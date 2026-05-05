import sqlite3
import os

DB_NAME = "scheme_finance.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def initialize_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    # 1. Accounts Table (For Cash in hand, Bank, Company Account, etc.)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_name TEXT UNIQUE NOT NULL,
        account_type TEXT NOT NULL, -- 'CASH', 'BANK', 'INCOME', 'EXPENSE'
        balance REAL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Insert default accounts
    default_accounts = [
        ('Cash in Hand', 'CASH'),
        ('Bank Account', 'BANK'),
        ('Company Commission', 'INCOME')
    ]
    for acc, acc_type in default_accounts:
        cursor.execute("INSERT OR IGNORE INTO accounts (account_name, account_type) VALUES (?, ?)", (acc, acc_type))
    
    # 2. Transactions Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER,
        related_account_id INTEGER,
        transaction_type TEXT, -- 'DEPOSIT', 'WITHDRAW', 'PAYMENT', 'PAYOUT', 'COMMISSION'
        amount REAL NOT NULL,
        description TEXT,
        transaction_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        FOREIGN KEY(related_account_id) REFERENCES accounts(id)
    )
    """)

    # 3. Scheme Master (Template for payments)
    # Check if total_value column exists, if not drop and recreate
    cursor.execute("PRAGMA table_info(scheme_master)")
    cols = [c[1] for c in cursor.fetchall()]
    if cols and "total_value" not in cols:
        cursor.execute("DROP TABLE scheme_master")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS scheme_master (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        total_value REAL NOT NULL,
        month_number INTEGER NOT NULL,
        payable_amount REAL,
        benefit_amount REAL,
        withdrawable_amount REAL,
        liability_emi REAL,
        UNIQUE(total_value, month_number)
    )
    """)
    
    def generate_scheme_data(total_value):
        A = total_value
        M = 20  # Number of Months
        B = A / M
        
        starting_kasaar = 0.23 * B
        kasaar_step = starting_kasaar / (M - 1)
        
        withdraw_increment = A * 0.01
        first_withdraw = A * 0.75
        
        data = []
        for n in range(1, M + 1):
            if n == 1:
                kasar = 0
                withdraw = A
            else:
                kasar = starting_kasaar - ((n - 2) * kasaar_step)
                withdraw = first_withdraw + ((n - 2) * withdraw_increment)
            
            due = B - kasar
            # Liability EMI is the full base installment B (repayment after withdrawal)
            liability_emi = B
            
            # Rounding to 2 decimal places for storage
            data.append((A, n, round(due, 2), round(kasar, 2), round(withdraw, 2), round(liability_emi, 2)))
        return data

    all_scheme_data = []
    for val in [200000, 500000, 1000000, 2000000]:
        all_scheme_data.extend(generate_scheme_data(val))
    
    for val, month, payable, benefit, withdrawable, liability in all_scheme_data:
        cursor.execute("""
        INSERT OR REPLACE INTO scheme_master 
        (total_value, month_number, payable_amount, benefit_amount, withdrawable_amount, liability_emi)
        VALUES (?, ?, ?, ?, ?, ?)
        """, (val, month, payable, benefit, withdrawable, liability))
    
    # 4. Customers / CIF Table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cif_number TEXT UNIQUE NOT NULL,
        name TEXT NOT NULL,
        phone TEXT,
        address TEXT,
        join_date TEXT NOT NULL,
        aadhar_number TEXT NOT NULL,
        aadhar_image_path TEXT,
        withdrawn_month INTEGER, -- NULL if not withdrawn
        status TEXT DEFAULT 'Active',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    # Migrations for existing database
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN aadhar_number TEXT")
    except:
        pass # Column already exists
        
    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN aadhar_image_path TEXT")
    except:
        pass # Column already exists

    try:
        cursor.execute("ALTER TABLE customers ADD COLUMN batch_id INTEGER")
    except:
        pass

    # 6b. Chit Batches
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chit_batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_name TEXT UNIQUE NOT NULL,
        chit_value REAL NOT NULL,
        starting_date TEXT,
        status TEXT DEFAULT 'Active',
        account_id INTEGER,
        FOREIGN KEY(account_id) REFERENCES accounts(id)
    )
    """)
    
    # 5. Customer Ledgers (Tracks payments per month per batch)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS customer_ledgers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        batch_id INTEGER,
        month_number INTEGER NOT NULL,
        due_amount REAL NOT NULL,
        paid_amount REAL DEFAULT 0,
        payment_date TEXT,
        receipt_number TEXT,
        status TEXT DEFAULT 'Pending', -- 'Pending', 'Partial', 'Paid'
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(batch_id) REFERENCES chit_batches(id),
        FOREIGN KEY(month_number) REFERENCES scheme_master(month_number),
        UNIQUE(customer_id, batch_id, month_number)
    )
    """)

    # 5a. Migration for customer_ledgers (Add batch_id and update unique constraint)
    cursor.execute("PRAGMA table_info(customer_ledgers)")
    cols = [c[1] for c in cursor.fetchall()]
    if "batch_id" not in cols:
        print("Migrating customer_ledgers to include batch_id...")
        cursor.execute("ALTER TABLE customer_ledgers RENAME TO customer_ledgers_old")
        cursor.execute("""
        CREATE TABLE customer_ledgers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            batch_id INTEGER,
            month_number INTEGER NOT NULL,
            due_amount REAL NOT NULL,
            paid_amount REAL DEFAULT 0,
            payment_date TEXT,
            receipt_number TEXT,
            status TEXT DEFAULT 'Pending',
            FOREIGN KEY(customer_id) REFERENCES customers(id),
            FOREIGN KEY(batch_id) REFERENCES chit_batches(id),
            FOREIGN KEY(month_number) REFERENCES scheme_master(month_number),
            UNIQUE(customer_id, batch_id, month_number)
        )
        """)
        # Copy data and join with customers to get the batch_id they were in
        cursor.execute("""
            INSERT INTO customer_ledgers (id, customer_id, batch_id, month_number, due_amount, paid_amount, payment_date, receipt_number, status)
            SELECT l.id, l.customer_id, c.batch_id, l.month_number, l.due_amount, l.paid_amount, l.payment_date, l.receipt_number, l.status
            FROM customer_ledgers_old l
            JOIN customers c ON l.customer_id = c.id
        """)
        cursor.execute("DROP TABLE customer_ledgers_old")

    # 5b. Batch Enrollments (Linking CIFs to multiple batches)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS batch_enrollments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        batch_id INTEGER,
        join_date TEXT,
        withdrawn_month INTEGER,
        status TEXT DEFAULT 'Active',
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        FOREIGN KEY(batch_id) REFERENCES chit_batches(id),
        UNIQUE(customer_id, batch_id)
    )
    """)

    # Migrate existing batch info from customers to batch_enrollments
    cursor.execute("SELECT COUNT(*) FROM batch_enrollments")
    if cursor.fetchone()[0] == 0:
        print("Migrating existing enrollments...")
        cursor.execute("""
            INSERT INTO batch_enrollments (customer_id, batch_id, join_date, withdrawn_month, status)
            SELECT id, batch_id, join_date, withdrawn_month, status
            FROM customers
            WHERE batch_id IS NOT NULL
        """)

    # 6. SHG Groups
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shg_groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_name TEXT UNIQUE NOT NULL,
        formation_date TEXT,
        leader_id INTEGER,
        deputy_leader_id INTEGER,
        starting_date TEXT,
        leader_name TEXT, -- Legacy
        phone TEXT, -- Legacy
        status TEXT DEFAULT 'Active',
        FOREIGN KEY(leader_id) REFERENCES customers(id),
        FOREIGN KEY(deputy_leader_id) REFERENCES customers(id)
    )
    """)

    # 6a. SHG Members
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shg_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        customer_id INTEGER,
        FOREIGN KEY(group_id) REFERENCES shg_groups(id),
        FOREIGN KEY(customer_id) REFERENCES customers(id),
        UNIQUE(group_id, customer_id)
    )
    """)


    # Migration for shg_groups
    try:
        cursor.execute("ALTER TABLE shg_groups ADD COLUMN leader_id INTEGER")
    except:
        pass 
    
    try:
        cursor.execute("ALTER TABLE shg_groups ADD COLUMN deputy_leader_id INTEGER")
    except:
        pass
        
    try:
        cursor.execute("ALTER TABLE shg_groups ADD COLUMN starting_date TEXT")
    except:
        pass


    # Migration for chit_batches (account_id)
    try:
        cursor.execute("ALTER TABLE chit_batches ADD COLUMN account_id INTEGER")
    except:
        pass

    # Ensure every batch has an account
    cursor.execute("SELECT id, batch_name, account_id FROM chit_batches")
    batches = cursor.fetchall()
    for bid, bname, acc_id in batches:
        if not acc_id:
            acc_name = f"Batch: {bname} Account"
            cursor.execute("INSERT OR IGNORE INTO accounts (account_name, account_type) VALUES (?, 'CHIT_FUND')", (acc_name,))
            cursor.execute("SELECT id FROM accounts WHERE account_name = ?", (acc_name,))
            new_acc_id = cursor.fetchone()[0]
            cursor.execute("UPDATE chit_batches SET account_id = ? WHERE id = ?", (new_acc_id, bid))

    # 7. SHG Loans
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS shg_loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER,
        loan_amount REAL NOT NULL,
        interest_rate REAL DEFAULT 0,
        duration_months INTEGER,
        start_date TEXT,
        status TEXT DEFAULT 'Active',
        FOREIGN KEY(group_id) REFERENCES shg_groups(id)
    )
    """)

    # 8. Individual Loans
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS individual_loans (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        customer_id INTEGER,
        loan_amount REAL NOT NULL,
        interest_rate REAL DEFAULT 0,
        duration_months INTEGER,
        start_date TEXT,
        status TEXT DEFAULT 'Active',
        FOREIGN KEY(customer_id) REFERENCES customers(id)
    )
    """)

    # 9. Loan Repayments (For both SHG and Individual)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS loan_repayments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        loan_type TEXT, -- 'SHG', 'INDIVIDUAL'
        loan_id INTEGER,
        repayment_amount REAL NOT NULL,
        interest_paid REAL DEFAULT 0,
        principal_paid REAL DEFAULT 0,
        repayment_date TEXT,
        status TEXT DEFAULT 'Paid'
    )
    """)
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    initialize_db()
    print("Database Initialized Successfully.")
