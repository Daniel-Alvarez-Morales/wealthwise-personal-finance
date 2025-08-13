"""
Database module for Personal Finance Application

Handles SQLite database operations for storing transactions and categories.
Provides persistent storage while maintaining all existing functionality.
"""

import sqlite3
import pandas as pd
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import hashlib

class FinanceDatabase:
    def __init__(self, db_path: str = "finance_data.db"):
        """
        Initialize the database connection and create tables if they don't exist.
        
        Args:
            db_path (str): Path to the SQLite database file
        """
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Create transactions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    transaction_hash TEXT UNIQUE NOT NULL,
                    fecha_valor DATE NOT NULL,
                    concepto TEXT NOT NULL,
                    importe REAL NOT NULL,
                    tipo TEXT NOT NULL,
                    category TEXT NOT NULL,
                    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create categories table for tracking category changes
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category_name TEXT UNIQUE NOT NULL,
                    keywords TEXT NOT NULL,
                    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Create index for faster lookups
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_transaction_hash 
                ON transactions(transaction_hash)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fecha_valor 
                ON transactions(fecha_valor)
            """)
            
            conn.commit()
            print("✅ Database initialized successfully")
    
    def generate_transaction_hash(self, fecha_valor: str, concepto: str, importe: float) -> str:
        """
        Generate a unique hash for a transaction to detect duplicates.
        
        Args:
            fecha_valor (str): Transaction date
            concepto (str): Transaction description
            importe (float): Transaction amount
            
        Returns:
            str: SHA-256 hash of the transaction
        """
        # Normalize the data for consistent hashing
        normalized_data = f"{fecha_valor}|{concepto.strip()}|{abs(importe):.2f}"
        return hashlib.sha256(normalized_data.encode('utf-8')).hexdigest()
    
    def transaction_exists(self, transaction_hash: str) -> bool:
        """
        Check if a transaction already exists in the database.
        
        Args:
            transaction_hash (str): Hash of the transaction
            
        Returns:
            bool: True if transaction exists, False otherwise
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM transactions WHERE transaction_hash = ?",
                (transaction_hash,)
            )
            return cursor.fetchone()[0] > 0
    
    def insert_transactions(self, df: pd.DataFrame) -> Tuple[int, int]:
        """
        Insert new transactions into the database, skipping duplicates.
        
        Args:
            df (pd.DataFrame): DataFrame with transaction data
            
        Returns:
            Tuple[int, int]: (new_transactions_added, duplicates_skipped)
        """
        new_count = 0
        duplicate_count = 0
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for _, row in df.iterrows():
                try:
                    # Generate hash for duplicate detection
                    transaction_hash = self.generate_transaction_hash(
                        row['Fecha valor'].strftime('%Y-%m-%d'),
                        row['Concepto'],
                        row['Importe']
                    )
                    
                    # Use INSERT OR IGNORE to handle duplicates gracefully
                    cursor.execute("""
                        INSERT OR IGNORE INTO transactions 
                        (transaction_hash, fecha_valor, concepto, importe, tipo, category)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        transaction_hash,
                        row['Fecha valor'].strftime('%Y-%m-%d'),
                        row['Concepto'],
                        row['Importe'],
                        row['Tipo'],
                        row['Category']
                    ))
                    
                    # Check if the row was actually inserted
                    if cursor.rowcount > 0:
                        new_count += 1
                        print(f"✅ Added: {row['Concepto'][:50]}...")
                    else:
                        duplicate_count += 1
                        print(f"⏭️  Skipping duplicate: {row['Concepto'][:50]}...")
                        
                except Exception as e:
                    print(f"❌ Error inserting transaction: {e}")
                    print(f"   Transaction: {row['Concepto'][:50]}...")
                    duplicate_count += 1
                    continue
            
            conn.commit()
        
        return new_count, duplicate_count
    
    def load_all_transactions(self) -> pd.DataFrame:
        """
        Load all transactions from the database.
        
        Returns:
            pd.DataFrame: All transactions with proper data types
        """
        with sqlite3.connect(self.db_path) as conn:
            query = """
                SELECT fecha_valor, concepto, importe, tipo, category
                FROM transactions
                ORDER BY fecha_valor DESC
            """
            df = pd.read_sql_query(query, conn)
            
            if not df.empty:
                # Convert data types to match the original format
                df['Fecha valor'] = pd.to_datetime(df['fecha_valor'])
                df['Concepto'] = df['concepto']
                df['Importe'] = df['importe'].astype(float)
                df['Tipo'] = df['tipo']
                df['Category'] = df['category']
                
                # Drop the original column names and keep the formatted ones
                df = df[['Fecha valor', 'Concepto', 'Importe', 'Tipo', 'Category']]
            
            return df
    
    def update_transaction_category(self, transaction_hash: str, new_category: str):
        """
        Update the category of a specific transaction.
        
        Args:
            transaction_hash (str): Hash of the transaction to update
            new_category (str): New category name
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE transactions 
                SET category = ?, last_modified = CURRENT_TIMESTAMP
                WHERE transaction_hash = ?
            """, (new_category, transaction_hash))
            conn.commit()
    
    def update_transactions_by_concept(self, concepto: str, new_category: str) -> int:
        """
        Update category for all transactions matching a specific concept.
        
        Args:
            concepto (str): Transaction concept to match
            new_category (str): New category name
            
        Returns:
            int: Number of transactions updated
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE transactions 
                SET category = ?, last_modified = CURRENT_TIMESTAMP
                WHERE concepto = ?
            """, (new_category, concepto))
            updated_count = cursor.rowcount
            conn.commit()
            return updated_count
    
    def sync_categories(self, categories_dict: Dict[str, List[str]]):
        """
        Sync categories from categories.json to the database.
        
        Args:
            categories_dict (Dict): Categories dictionary from JSON
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            for category_name, keywords in categories_dict.items():
                keywords_json = json.dumps(keywords)
                
                cursor.execute("""
                    INSERT OR REPLACE INTO categories (category_name, keywords, last_modified)
                    VALUES (?, ?, CURRENT_TIMESTAMP)
                """, (category_name, keywords_json))
            
            conn.commit()
    
    def get_database_stats(self) -> Dict[str, int]:
        """
        Get statistics about the database.
        
        Returns:
            Dict: Database statistics
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            
            # Total transactions
            cursor.execute("SELECT COUNT(*) FROM transactions")
            total_transactions = cursor.fetchone()[0]
            
            # Transactions by category
            cursor.execute("""
                SELECT category, COUNT(*) 
                FROM transactions 
                GROUP BY category 
                ORDER BY COUNT(*) DESC
            """)
            category_counts = dict(cursor.fetchall())
            
            # Date range
            cursor.execute("""
                SELECT MIN(fecha_valor), MAX(fecha_valor) 
                FROM transactions
            """)
            date_range = cursor.fetchone()
            
            return {
                'total_transactions': total_transactions,
                'category_counts': category_counts,
                'date_range': date_range
            }
    
    def close(self):
        """Close database connection (if needed for cleanup)."""
        # SQLite connections are automatically closed when using context managers
        pass
