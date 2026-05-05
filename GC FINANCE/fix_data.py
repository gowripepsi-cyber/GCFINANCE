import scheme_db
from PySide6.QtWidgets import QApplication
import scheme_app

def fix_data():
    conn = scheme_db.get_connection()
    cursor = conn.cursor()

    # 1. Revert old ledgers to Batch 3
    cursor.execute('UPDATE customer_ledgers SET batch_id = 3 WHERE id <= 220')

    # 2. Ensure all these customers are enrolled in Batch 3
    cursor.execute('''
        INSERT OR IGNORE INTO batch_enrollments (customer_id, batch_id, join_date, status)
        SELECT DISTINCT customer_id, 3, "2026-04-26", "Active" 
        FROM customer_ledgers WHERE batch_id = 3
    ''')

    conn.commit()

    # 3. Find all customers enrolled in Batch 4
    cursor.execute('SELECT customer_id FROM batch_enrollments WHERE batch_id = 4')
    batch_4_customers = [row[0] for row in cursor.fetchall()]

    conn.close()

    # 4. Allocate fresh ledgers for Batch 4
    app_instance = QApplication.instance()
    if not app_instance:
        app_instance = QApplication([])
    
    app = scheme_app.SchemeFinanceApp()
    app.allocate_batch_ledgers(4, batch_4_customers)

    print('Data fixed successfully!')

if __name__ == '__main__':
    fix_data()
