"""
Personal Finance Analysis Tool

A Streamlit application for analyzing bank statement CSV files with categorization,
filtering by month, and comprehensive financial visualizations.
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import json
import os
import importlib
import sys

# Force reload of OpenAI service module to ensure latest changes are loaded
if 'open_ai_service' in sys.modules:
    importlib.reload(sys.modules['open_ai_service'])

from open_ai_service import OpenAIService
from database import FinanceDatabase

# Configuration
st.set_page_config(
    page_title="FinanceTracker Pro", 
    page_icon="💰", 
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Constants
CATEGORIES_FILE = "categories.json"
UNCATEGORIZED_CATEGORY = "Uncategorized"

# Custom CSS for modern financial app styling
def load_custom_css():
    """
    Load custom CSS from external file to create a modern, professional financial app appearance.
    """
    try:
        with open("styles.css", "r") as f:
            css_content = f.read()
        st.markdown(f"<style>{css_content}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        st.warning("CSS file not found. Using default styling.")
    except Exception as e:
        st.error(f"Error loading CSS: {e}")

# ============================================================================
# DATA MANAGEMENT FUNCTIONS
# ============================================================================

def load_categories():
    """
    Load categories from JSON file or initialize with default structure.
    
    Returns:
        dict: Categories dictionary with category names as keys and keyword lists as values
    """
    if os.path.exists(CATEGORIES_FILE):
        with open(CATEGORIES_FILE, "r") as f:
            return json.load(f)
    else:
        return {UNCATEGORIZED_CATEGORY: []}

def save_categories():
    """
    Save current categories from session state to JSON file with pretty formatting.
    """
    with open(CATEGORIES_FILE, "w") as f:
        json.dump(st.session_state.categories, f, indent=2, ensure_ascii=False)

def load_transactions(file):
    """
    Load and process bank statement CSV file.
    
    Args:
        file: Uploaded CSV file from Streamlit file_uploader
        
    Returns:
        pandas.DataFrame: Processed DataFrame with cleaned data and categories, or None if error
    """
    try:
        # Load and clean CSV data
        df = pd.read_csv(file)
        df.columns = [col.strip() for col in df.columns]
        
        # Drop Saldo column if it exists
        if 'Saldo' in df.columns:
            df = df.drop('Saldo', axis=1)
        
        
        # Clean and convert monetary amounts
        df['Importe'] = df['Importe'].str.replace('.', '').str.replace(',', '.').str.replace('€', '').astype(float)
        
        # Create transaction type column (Debit/Credit)
        df['Tipo'] = df['Importe'].apply(lambda x: 'Debit' if x < 0 else 'Credit')
        
        # Convert all amounts to positive values
        df['Importe'] = df['Importe'].abs()
        
        # Parse dates
        df['Fecha valor'] = pd.to_datetime(df['Fecha valor'], format='%d/%m/%Y')

        # Initial categorization
        df = categorize_transactions(df)
        
        # Save new transactions to database and get statistics
        new_count, duplicate_count = st.session_state.db.insert_transactions(df)
        
        # Update the all_transactions_df with latest data from database
        st.session_state.all_transactions_df = st.session_state.db.load_all_transactions()
        
        # Always display database operation results
        col1, col2 = st.columns(2)
        with col1:
            if new_count > 0:
                st.success(f"✅ Added {new_count} new transactions to database")
            else:
                st.info(f"📊 No new transactions added")
        with col2:
            if duplicate_count > 0:
                st.warning(f"⏭️ Skipped {duplicate_count} duplicate transactions")
            else:
                st.info(f"🆕 All transactions were new")
        
        # Summary message
        total_processed = new_count + duplicate_count
        if duplicate_count == total_processed and duplicate_count > 0:
            st.info(f"🔄 File already processed - all {duplicate_count} transactions were duplicates")
        elif new_count > 0:
            st.success(f"🎉 Successfully processed {total_processed} transactions ({new_count} new, {duplicate_count} duplicates)")
        
        # Sync categories to database
        st.session_state.db.sync_categories(st.session_state.categories)
        
        # Check for uncategorized transactions and offer AI categorization
        uncategorized_df = df[df['Category'] == UNCATEGORIZED_CATEGORY]
        uncategorized_count = len(uncategorized_df)
        
        if uncategorized_count > 0:
            st.warning(f"⚠️ Found {uncategorized_count} uncategorized transactions.")
            
            # Console logging for initial uncategorized transactions
            print(f"\n⚠️  FOUND {uncategorized_count} UNCATEGORIZED TRANSACTIONS:")
            print("=" * 80)
            for i, (_, row) in enumerate(uncategorized_df.iterrows(), 1):
                concept_display = row['Concepto'][:70] + "..." if len(row['Concepto']) > 70 else row['Concepto']
                date_str = row['Fecha valor'].strftime('%d/%m/%Y') if 'Fecha valor' in row else 'N/A'
                amount_str = f"{row['Importe']:.2f}€" if 'Importe' in row else 'N/A'
                print(f"{i:2d}. [{date_str}] {amount_str} - {concept_display}")
            print("=" * 80)
            
            # Add AI categorization button
            col1, col2 = st.columns([1, 3])
            with col1:
                if st.button("🤖 AI Categorize", help="Let AI analyze and categorize uncategorized transactions"):
                    df = ai_categorize_uncategorized_transactions(df)
                    # Update database with AI categorized transactions
                    st.session_state.db.insert_transactions(df)
                    st.session_state.all_transactions_df = st.session_state.db.load_all_transactions()
                    st.rerun()  # Refresh to show updated data
            with col2:
                st.info("💡 Click 'AI Categorize' to let AI help categorize your transactions automatically!")
        
        return df
    except Exception as e:
        st.error(f"Error loading transactions: {e}")
        return None

def categorize_transactions(df):
    """
    Automatically categorize transactions based on keywords in transaction descriptions.
    
    Args:
        df (pandas.DataFrame): DataFrame with transaction data
        
    Returns:
        pandas.DataFrame: DataFrame with added 'Category' column
    """
    df['Category'] = UNCATEGORIZED_CATEGORY
    
    for category, keywords in st.session_state.categories.items():
        if category == UNCATEGORIZED_CATEGORY or not keywords:
            continue
        
        lowered_keywords = [keyword.lower().strip() for keyword in keywords]
        for idx, row in df.iterrows():
            details = row['Concepto'].lower().strip()
            if any(keyword in details for keyword in lowered_keywords):
                df.at[idx, 'Category'] = category
                
    return df

def ai_categorize_uncategorized_transactions(df):
    """
    Use AI to categorize transactions that remain uncategorized after initial categorization.
    
    Args:
        df (pandas.DataFrame): DataFrame with transactions and categories
        
    Returns:
        pandas.DataFrame: DataFrame with AI-updated categories
    """
    # Find uncategorized transactions
    uncategorized_df = df[df['Category'] == UNCATEGORIZED_CATEGORY]
    
    if len(uncategorized_df) == 0:
        st.success("🎉 All transactions are already categorized!")
        return df
    
    # Get unique uncategorized transaction descriptions (limit to avoid API costs)
    uncategorized_descriptions = uncategorized_df['Concepto'].unique()[:20]  # Limit to 20 unique descriptions
    
    if len(uncategorized_descriptions) == 0:
        return df
    
    st.info(f"🤖 Found {len(uncategorized_descriptions)} unique uncategorized transactions. Asking AI for help...")
    
    # Console logging - Start of AI categorization
    print("\n" + "🚀" * 20)
    print("🤖 STARTING AI CATEGORIZATION PROCESS")
    print("🚀" * 20)
    print(f"📊 Processing {len(uncategorized_descriptions)} unique uncategorized transactions")
    
    try:
        # Initialize AI service
        print("🔧 Initializing OpenAI service...")
        ai_service = OpenAIService()
        print("✅ OpenAI service initialized successfully")
        
        # Debug: Check if method exists
        print(f"🔍 Checking if method exists: {hasattr(ai_service, 'categorize_transactions_ai')}")
        if not hasattr(ai_service, 'categorize_transactions_ai'):
            print("❌ METHOD NOT FOUND!")
            st.error("❌ AI categorization method not found. Please restart the Streamlit app.")
            st.info("💡 Try stopping the app (Ctrl+C) and running `streamlit run main.py` again.")
            return df
        else:
            print("✅ Method found, proceeding with AI call...")
        
        # Prepare current categories as JSON string
        print("📝 Preparing categories JSON for AI...")
        current_categories_json = json.dumps(st.session_state.categories, indent=2, ensure_ascii=False)
        print(f"✅ Categories JSON prepared ({len(current_categories_json)} characters)")
        
        # Get AI categorization suggestions
        # Log the transactions being sent to AI
        print("📋 TRANSACTIONS SENT TO AI:")
        for i, desc in enumerate(uncategorized_descriptions[:10], 1):
            print(f"   {i}. {desc[:60]}{'...' if len(desc) > 60 else ''}")
        if len(uncategorized_descriptions) > 10:
            print(f"   ... and {len(uncategorized_descriptions) - 10} more")
        
        print("🧠 Calling AI categorization service...")
        with st.spinner("🧠 AI is analyzing uncategorized transactions..."):
            updated_categories = ai_service.categorize_transactions_ai(
                current_categories_json, 
                uncategorized_descriptions.tolist()
            )
            print("🔄 AI categorization call completed")
            
            # Debug: Show what uncategorized descriptions were sent to AI
            st.info(f"🔍 Debug: Sent {len(uncategorized_descriptions)} uncategorized descriptions to AI")
            with st.expander("View uncategorized descriptions sent to AI"):
                for i, desc in enumerate(uncategorized_descriptions[:5], 1):
                    st.write(f"{i}. {desc}")
                if len(uncategorized_descriptions) > 5:
                    st.write(f"... and {len(uncategorized_descriptions) - 5} more")
        
        # Console logging for AI response
        print(f"🔄 AI Response received: {updated_categories is not None}")
        
        if updated_categories:
            # Count how many new keywords were added
            original_keyword_count = sum(len(keywords) for keywords in st.session_state.categories.values())
            new_keyword_count = sum(len(keywords) for keywords in updated_categories.values())
            
            # Console logging for keyword analysis
            print(f"📊 KEYWORD ANALYSIS:")
            print(f"   Original keywords: {original_keyword_count}")
            print(f"   New keywords: {new_keyword_count}")
            print(f"   Keywords added: {new_keyword_count - original_keyword_count}")
            
            # Debug: Show what AI returned
            st.info(f"🔍 Debug: AI returned categories with {new_keyword_count} total keywords (originally {original_keyword_count})")
            
            if new_keyword_count > original_keyword_count:
                # Store original categories for comparison
                original_categories = st.session_state.categories.copy()
                
                # Get original uncategorized transactions to track what gets categorized
                original_uncategorized_df = df[df['Category'] == UNCATEGORIZED_CATEGORY].copy()
                
                # Count uncategorized transactions before update
                uncategorized_before = len(original_uncategorized_df)
                
                # Update session state categories
                st.session_state.categories = updated_categories
                
                # Save updated categories to file
                save_categories()
                
                # Re-categorize all transactions with updated categories
                df = categorize_transactions(df)
                
                # Count uncategorized transactions after update
                uncategorized_after = len(df[df['Category'] == UNCATEGORIZED_CATEGORY])
                transactions_categorized = uncategorized_before - uncategorized_after
                
                # Show success message with transaction count
                new_keywords_added = new_keyword_count - original_keyword_count
                
                if transactions_categorized > 0:
                    st.success(f"🎉 AI successfully categorized {transactions_categorized} transactions!")
                    st.info(f"✨ Added {new_keywords_added} new keywords to existing categories")
                    
                    # Find and show which specific transactions were newly categorized
                    newly_categorized_details = []
                    
                    # Console logging for newly categorized transactions
                    print("\n" + "=" * 60)
                    print("🎯 NEWLY CATEGORIZED TRANSACTIONS")
                    print("=" * 60)
                    
                    for _, orig_row in original_uncategorized_df.iterrows():
                        # Find the same transaction in the updated dataframe
                        matching_rows = df[
                            (df['Concepto'] == orig_row['Concepto']) & 
                            (df['Fecha valor'] == orig_row['Fecha valor']) &
                            (df['Importe'] == orig_row['Importe'])
                        ]
                        
                        if not matching_rows.empty:
                            new_category = matching_rows.iloc[0]['Category']
                            if new_category != UNCATEGORIZED_CATEGORY:
                                # Console logging
                                print(f"✅ '{new_category}': {orig_row['Concepto']}")
                                
                                # Truncate long descriptions for better display
                                concept_display = orig_row['Concepto'][:50] + "..." if len(orig_row['Concepto']) > 50 else orig_row['Concepto']
                                newly_categorized_details.append(f"• **{new_category}**: {concept_display}")
                    
                    print("=" * 60)
                    
                    # Display the newly categorized transactions
                    if newly_categorized_details:
                        st.markdown("### 🎯 **Newly Categorized Transactions:**")
                        for detail in newly_categorized_details[:10]:  # Show max 10 to avoid cluttering
                            st.markdown(detail)
                        
                        if len(newly_categorized_details) > 10:
                            st.info(f"📋 ... and {len(newly_categorized_details) - 10} more transactions were categorized")
                    
                else:
                    st.success(f"✨ AI added {new_keywords_added} new keywords, but no additional transactions were categorized this time")
                
                # Show which categories were updated
                updated_cats = []
                for cat, keywords in updated_categories.items():
                    if cat in original_categories and len(keywords) > len(original_categories.get(cat, [])):
                        updated_cats.append(cat)
                
                if updated_cats:
                    st.info(f"📝 Updated categories: {', '.join(updated_cats)}")
                
                # Show remaining uncategorized count
                if uncategorized_after > 0:
                    st.warning(f"⚠️ {uncategorized_after} transactions remain uncategorized and may need manual review")
                    
                    # Console logging for remaining uncategorized transactions
                    remaining_uncategorized = df[df['Category'] == UNCATEGORIZED_CATEGORY]
                    print(f"\n⚠️  STILL UNCATEGORIZED ({len(remaining_uncategorized)} transactions):")
                    print("=" * 60)
                    for i, (_, row) in enumerate(remaining_uncategorized.iterrows(), 1):
                        concept_display = row['Concepto'][:80] + "..." if len(row['Concepto']) > 80 else row['Concepto']
                        print(f"{i:2d}. {concept_display}")
                    print("=" * 60)
                else:
                    st.success("🎊 All transactions are now categorized!")
                    print("🎊 ALL TRANSACTIONS NOW CATEGORIZED!")
                
            else:
                print("⚠️  NO NEW KEYWORDS ADDED")
                print("   Reason: AI returned same categories without new keywords")
                
                # Show which transactions remain uncategorized
                still_uncategorized = df[df['Category'] == UNCATEGORIZED_CATEGORY]
                if len(still_uncategorized) > 0:
                    print(f"\n⚠️  TRANSACTIONS STILL UNCATEGORIZED ({len(still_uncategorized)} total):")
                    print("=" * 60)
                    for i, (_, row) in enumerate(still_uncategorized.iterrows(), 1):
                        concept_display = row['Concepto'][:80] + "..." if len(row['Concepto']) > 80 else row['Concepto']
                        print(f"{i:2d}. {concept_display}")
                    print("=" * 60)
                
                st.info("🤔 AI couldn't confidently categorize the remaining transactions. They'll stay as 'Uncategorized' for manual review.")
                st.info("💡 AI may have returned the same categories without new keywords.")
        else:
            print("❌ NO CATEGORIES RETURNED FROM AI")
            print("   This indicates an API failure or invalid response")
            st.error("❌ AI categorization failed - no categories returned.")
            
            # Show detailed error information if available
            if hasattr(ai_service, 'last_error'):
                st.error(f"🔍 Error Details: {ai_service.last_error}")
            
            if hasattr(ai_service, 'last_ai_response'):
                st.warning("🤖 Raw AI Response:")
                st.code(ai_service.last_ai_response, language="text")
            
            st.info("⚠️ This could be due to:")
            st.write("• OpenAI API configuration issues")
            st.write("• Invalid JSON response from AI")
            st.write("• Network connectivity problems")
            st.write("• AI returning text instead of JSON")
            
    except Exception as e:
        print(f"❌ EXCEPTION in AI categorization: {str(e)}")
        print("🚀" * 20)
        st.error(f"❌ Error during AI categorization: {str(e)}")
        st.info("💡 Make sure your OpenAI API key is configured correctly.")
    
    print("🏁 AI categorization process finished")
    print("🚀" * 20)
    return df

def add_keywords_to_category(category, keywords):
    """
    Add keywords to a specific category for automatic transaction categorization.
    
    Args:
        category (str): Category name
        keywords (str): Keywords to add (will be stripped)
        
    Returns:
        bool: True if successfully added, False if already exists
    """
    keyword = keywords.strip()
    if keywords and keywords not in st.session_state.categories[category]:
        st.session_state.categories[category].append(keyword)
        save_categories()
        st.success(f"Keyword {keyword} added to category {category}")
        return True
    else:
        st.error(f"Keyword {keyword} already exists in category {category}")
        return False

def format_bank_statement_for_ai(debits_df, credits_df, selected_month):
    """
    Format bank statement data into a structured format for OpenAI analysis.
    
    Args:
        debits_df (pandas.DataFrame): Debit transactions
        credits_df (pandas.DataFrame): Credit transactions  
        selected_month (str): Selected month filter
        
    Returns:
        str: Formatted bank statement data as JSON string
    """
    # Calculate summary statistics (excluding savings from expenses)
    total_income = credits_df['Importe'].sum()
    
    # Separate savings from expenses
    savings_df = debits_df[debits_df['Category'] == 'Savings']
    expenses_df = debits_df[debits_df['Category'] != 'Savings']
    
    total_savings = savings_df['Importe'].sum()
    total_expenses = expenses_df['Importe'].sum()
    balance = total_income - (total_expenses + total_savings)
    
    # Get category breakdown (excluding savings from expenses)
    category_breakdown = expenses_df.groupby('Category')['Importe'].sum().to_dict()
    savings_breakdown = {'Savings': float(total_savings)} if total_savings > 0 else {}
    
    # Format transaction data
    debit_transactions = []
    for _, row in debits_df.head(20).iterrows():  # Limit to top 20 for API efficiency
        debit_transactions.append({
            "date": row['Fecha valor'].strftime('%Y-%m-%d'),
            "description": row['Concepto'],
            "amount": float(row['Importe']),
            "category": row['Category']
        })
    
    credit_transactions = []
    for _, row in credits_df.head(10).iterrows():  # Limit to top 10 credits
        credit_transactions.append({
            "date": row['Fecha valor'].strftime('%Y-%m-%d'),
            "description": row['Concepto'],
            "amount": float(row['Importe'])
        })
    
    # Create structured data
    bank_statement_data = {
        "period": selected_month if selected_month != 'All Months' else 'All available data',
        "summary": {
            "total_income": float(total_income),
            "total_expenses": float(total_expenses),
            "total_savings": float(total_savings),
            "net_balance": float(balance),
            "transaction_count": {
                "debits": len(debits_df),
                "credits": len(credits_df),
                "expenses": len(expenses_df),
                "savings": len(savings_df)
            }
        },
        "expense_categories": category_breakdown,
        "savings_categories": savings_breakdown,
        "recent_debits": debit_transactions,
        "recent_credits": credit_transactions
    }
    
    return json.dumps(bank_statement_data, indent=2, ensure_ascii=False)

# ============================================================================
# DATA FILTERING FUNCTIONS
# ============================================================================

def prepare_monthly_data(df):
    """
    Prepare data for monthly filtering by extracting month-year periods.
    
    Args:
        df (pandas.DataFrame): Transaction DataFrame
        
    Returns:
        tuple: (DataFrame with Month_Year column, sorted list of available months)
    """
    df['Month_Year'] = df['Fecha valor'].dt.to_period('M')
    available_months = sorted(df['Month_Year'].unique(), reverse=True)
    return df, available_months

def filter_data_by_month(df, selected_month):
    """
    Filter DataFrame by selected month or return all data.
    
    Args:
        df (pandas.DataFrame): Full transaction DataFrame
        selected_month (str): Selected month string or 'All Months'
        
    Returns:
        pandas.DataFrame: Filtered DataFrame
    """
    if selected_month == 'All Months':
        return df.copy()
    else:
        return df[df['Month_Year'] == selected_month].copy()

def separate_debits_credits(df):
    """
    Separate transactions into debits and credits, sorted by date.
    
    Args:
        df (pandas.DataFrame): Filtered transaction DataFrame
        
    Returns:
        tuple: (debits_df, credits_df) both sorted by date descending
    """
    debits_df = df[df['Tipo'] == 'Debit'].sort_values(by='Fecha valor', ascending=False).copy()
    credits_df = df[df['Tipo'] == 'Credit'].sort_values(by='Fecha valor', ascending=False).copy()
    return debits_df, credits_df

# ============================================================================
# UI COMPONENT FUNCTIONS
# ============================================================================

def render_month_selector(available_months):
    """
    Render month selection dropdown with change detection.
    
    Args:
        available_months (list): List of available month periods
        
    Returns:
        str: Selected month string
    """
    col1, col2 = st.columns([1, 3])
    with col1:
        selected_month = st.selectbox(
            "Select Month:",
            options=['All Months'] + [str(month) for month in available_months],
            index=0,
            key="month_selector"
        )
    return selected_month

def render_summary_metrics(debits_df, credits_df):
    """
    Render summary financial metrics in a 4-column layout.
    
    Args:
        debits_df (pandas.DataFrame): Debit transactions
        credits_df (pandas.DataFrame): Credit transactions
    """
    col1, col2, col3, col4 = st.columns(4)
    
    total_income = credits_df['Importe'].sum()
    
    # Separate savings from expenses
    savings_df = debits_df[debits_df['Category'] == 'Savings']
    expenses_df = debits_df[debits_df['Category'] != 'Savings']
    
    total_savings = savings_df['Importe'].sum()
    total_expenses = expenses_df['Importe'].sum()
    balance = total_income - (total_expenses + total_savings)
    
    with col1:
        st.metric("💰 Total Income", f"{total_income:,.2f} €")
    with col2:
        st.metric("💸 Total Expenses", f"{total_expenses:,.2f} €")
    with col3:
        st.metric("🏦 Total Savings", f"{total_savings:,.2f} €")
    with col4:
        delta_color = "normal" if balance >= 0 else "inverse"
        st.metric("📊 Balance", f"{balance:,.2f} €", delta=f"{balance:,.2f} €")

def render_category_management():
    """
    Render category management UI (add new categories).
    
    Returns:
        tuple: (new_category, add_button_clicked)
    """
    new_category = st.text_input("New Category")
    add_button = st.button("Add Category")
    
    if add_button and new_category:
        if new_category not in st.session_state.categories:
            st.session_state.categories[new_category] = []
            save_categories()
            st.success(f"Category {new_category} added successfully")
        else:
            st.error(f"Category {new_category} already exists")
    
    return new_category, add_button

def render_transaction_editor(debits_df):
    """
    Render interactive transaction editor with category selection and search functionality.
    
    Args:
        debits_df (pandas.DataFrame): Debit transactions DataFrame
        
    Returns:
        pandas.DataFrame: Edited DataFrame from user interactions
    """
    st.subheader("Your Expenses")
    
    # Add search functionality
    col1, col2 = st.columns([2, 1])
    with col1:
        search_term = st.text_input(
            "🔍 Search by Concepto (Transaction Description)",
            placeholder="Type to filter transactions...",
            help="Search for specific merchants, services, or transaction descriptions"
        )
    with col2:
        st.write("")  # Empty space for alignment
        if st.button("🗑️ Clear Search", help="Clear the search filter"):
            st.rerun()
    
    # Filter the dataframe based on search term
    filtered_debits_df = debits_df.copy()
    if search_term:
        # Case-insensitive search in the Concepto column
        mask = filtered_debits_df['Concepto'].str.contains(search_term, case=False, na=False)
        filtered_debits_df = filtered_debits_df[mask]
        
        # Show search results info
        if len(filtered_debits_df) > 0:
            st.info(f"🔍 Found {len(filtered_debits_df)} transactions matching '{search_term}'")
        else:
            st.warning(f"❌ No transactions found matching '{search_term}'")
            return debits_df  # Return original if no matches
    
    # Display the filtered data editor
    edited_df = st.data_editor(
        filtered_debits_df[['Fecha valor', 'Concepto', 'Importe', 'Category']],
        column_config={
            "Fecha valor": st.column_config.DateColumn(
                format="DD/MM/YYYY"
            ),
            "Importe": st.column_config.NumberColumn(
                format="%.2f €"
            ),
            "Category": st.column_config.SelectboxColumn(
                "Category",
                options=list(st.session_state.categories.keys())
            )
        },
        hide_index=True,
        use_container_width=True,
        key=f"category_editor_{hash(search_term) if search_term else 'all'}"  # Unique key for different searches
    )
    
    return edited_df

def process_category_changes(edited_df):
    """
    Process changes made in the transaction editor and update categories.
    
    Args:
        edited_df (pandas.DataFrame): Edited DataFrame from transaction editor
    """
    save_button = st.button("Save Changes", type="primary")
    if save_button:
        changes_made = 0
        for idx, row in edited_df.iterrows():
            new_category = row['Category']
            if new_category == st.session_state.debits_df.at[idx, 'Category']:
                continue
            
            details = row['Concepto']
            st.session_state.debits_df.at[idx, 'Category'] = new_category
            
            # Update database for all transactions with this concept
            updated_count = st.session_state.db.update_transactions_by_concept(details, new_category)
            
            # Add keyword to category
            add_keywords_to_category(new_category, details)
            
            # Sync categories to database
            st.session_state.db.sync_categories(st.session_state.categories)
            
            changes_made += updated_count
            st.success(f"✅ Updated {updated_count} transactions with concept '{details[:50]}...' to category '{new_category}'")
        
        if changes_made > 0:
            # Refresh data from database
            st.session_state.all_transactions_df = st.session_state.db.load_all_transactions()
            st.info(f"🔄 Refreshed data - {changes_made} total changes applied to database")
            st.rerun()

def render_expense_summary(debits_df):
    """
    Render expense summary with category breakdown and pie chart (excluding savings).
    
    Args:
        debits_df (pandas.DataFrame): Debit transactions DataFrame
    """
    st.subheader("Expenses Summary")
    
    # Exclude savings from expenses summary
    expenses_df = debits_df[debits_df['Category'] != 'Savings']
    
    # Calculate category totals for expenses only
    category_totals = expenses_df.groupby('Category')['Importe'].sum().reset_index()
    category_totals = category_totals.sort_values(by='Importe', ascending=False)
    
    # Display summary table
    st.dataframe(category_totals, column_config={
        "Importe": st.column_config.NumberColumn(
            format="%.2f €"
        )
    })
    
    # Display pie chart with clean styling
    fig = px.pie(
        category_totals, 
        values='Importe', 
        names='Category', 
        title='💼 Expenses by Category',
        color_discrete_sequence=px.colors.qualitative.Set3
    )
    fig.update_layout(
        title_font_size=20,
        title_font_family="Inter",
        title_font_color="#1f2937",
        title_x=0.5,
        font_family="Inter",
        font_color="#1f2937",
        plot_bgcolor='white',
        paper_bgcolor='white',
        legend=dict(
            font=dict(color="#1f2937")
        )
    )
    fig.update_traces(
        textfont_color="#1f2937",
        hoverlabel=dict(
            bgcolor="white",
            bordercolor="#1f2937",
            font=dict(color="#1f2937", size=14)
        )
    )
    st.plotly_chart(fig, use_container_width=True)

def render_credits_tab(credits_df):
    """
    Render the credits/income tab content.
    
    Args:
        credits_df (pandas.DataFrame): Credit transactions DataFrame
    """
    st.subheader("Credits/Income Transactions")
    

    
    st.write(credits_df)

def render_savings_tab(debits_df):
    """
    Render savings transactions tab with detailed analysis and visualizations.
    
    Args:
        debits_df (pandas.DataFrame): All debit transactions DataFrame
    """
    st.subheader("🏦 Savings Management")
    
    # Filter only savings transactions
    savings_df = debits_df[debits_df['Category'] == 'Savings'].copy()
    
    if savings_df.empty:
        st.info("💡 **No savings transactions found!** Start categorizing your savings transfers and deposits as 'Savings' to track them here.")
        st.markdown("""
        ### 🤔 **What should be categorized as Savings?**
        - ✅ Transfers to savings accounts
        - ✅ Investment contributions
        - ✅ Retirement fund deposits
        - ✅ Emergency fund contributions
        - ✅ Fixed deposits
        - ❌ Don't include regular expenses here
        """)
        return
    
    # Savings Summary Metrics
    st.markdown("### 📊 Savings Overview")
    
    total_savings = savings_df['Importe'].sum()
    avg_savings = savings_df['Importe'].mean()
    savings_count = len(savings_df)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("🏦 Total Savings", f"{total_savings:,.2f} €")
    with col2:
        st.metric("📈 Average Savings", f"{avg_savings:,.2f} €")
    with col3:
        st.metric("📋 Savings Transactions", f"{savings_count}")
    
    # Savings transactions over time visualization
    st.markdown("### 📈 Savings Timeline")
    
    if len(savings_df) > 1:
        # Sort by date for timeline
        savings_timeline = savings_df.sort_values('Fecha valor').copy()
        savings_timeline['Cumulative_Savings'] = savings_timeline['Importe'].cumsum()
        
        # Create line chart showing cumulative savings
        fig = px.line(
            savings_timeline, 
            x='Fecha valor', 
            y='Cumulative_Savings',
            title='🎯 Cumulative Savings Growth',
            labels={'Cumulative_Savings': 'Cumulative Savings (€)', 'Fecha valor': 'Date'}
        )
        fig.update_layout(
            title_font_size=20,
            title_font_family="Inter",
            title_font_color="#1f2937",
            title_x=0.5,
            font_family="Inter",
            font_color="#1f2937",
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(gridcolor='lightgray'),
            yaxis=dict(gridcolor='lightgray')
        )
        fig.update_traces(line_color='#10b981', line_width=3)
        st.plotly_chart(fig, use_container_width=True)
        
        # Monthly savings bar chart
        savings_timeline['Month'] = savings_timeline['Fecha valor'].dt.to_period('M').astype(str)
        monthly_savings = savings_timeline.groupby('Month')['Importe'].sum().reset_index()
        
        fig2 = px.bar(
            monthly_savings,
            x='Month',
            y='Importe',
            title='💰 Monthly Savings Contributions',
            labels={'Importe': 'Savings Amount (€)', 'Month': 'Month'},
            color='Importe',
            color_continuous_scale='Greens'
        )
        fig2.update_layout(
            title_font_size=20,
            title_font_family="Inter",
            title_font_color="#1f2937",
            title_x=0.5,
            font_family="Inter",
            font_color="#1f2937",
            plot_bgcolor='white',
            paper_bgcolor='white',
            xaxis=dict(gridcolor='lightgray'),
            yaxis=dict(gridcolor='lightgray'),
            showlegend=False
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # Detailed savings transactions table
    st.markdown("### 📋 All Savings Transactions")
    
    # Add search functionality for savings
    search_term = st.text_input("🔍 Search savings transactions by concept:", key="savings_search")
    
    # Filter savings by search term
    if search_term:
        mask = savings_df['Concepto'].str.contains(search_term, case=False, na=False)
        filtered_savings_df = savings_df[mask]
        st.info(f"🔍 Showing {len(filtered_savings_df)} of {len(savings_df)} savings transactions matching '{search_term}'")
    else:
        filtered_savings_df = savings_df
    
    # Display savings transactions with proper formatting
    if not filtered_savings_df.empty:
        # Sort by date (newest first)
        filtered_savings_df = filtered_savings_df.sort_values('Fecha valor', ascending=False)
        
        # Display formatted table
        st.dataframe(
            filtered_savings_df[['Fecha valor', 'Concepto', 'Importe', 'Category']],
            column_config={
                "Fecha valor": st.column_config.DateColumn(
                    "📅 Date",
                    format="DD/MM/YYYY"
                ),
                "Concepto": st.column_config.TextColumn(
                    "💳 Description",
                    width="large"
                ),
                "Importe": st.column_config.NumberColumn(
                    "💰 Amount",
                    format="%.2f €"
                ),
                "Category": st.column_config.TextColumn(
                    "🏷️ Category"
                )
            },
            use_container_width=True,
            hide_index=True
        )
        
        # Savings insights
        st.markdown("### 💡 Savings Insights")
        col1, col2 = st.columns(2)
        
        with col1:
            # Largest savings transaction
            max_savings = filtered_savings_df.loc[filtered_savings_df['Importe'].idxmax()]
            st.success(f"🎯 **Largest Savings**: {max_savings['Importe']:.2f} € on {max_savings['Fecha valor'].strftime('%d/%m/%Y')}")
            
        with col2:
            # Most recent savings
            recent_savings = filtered_savings_df.iloc[0]  # Already sorted by date desc
            st.info(f"🕐 **Most Recent**: {recent_savings['Importe']:.2f} € on {recent_savings['Fecha valor'].strftime('%d/%m/%Y')}")
        
        # Savings frequency analysis
        if len(filtered_savings_df) > 2:
            # Calculate average days between savings
            date_diffs = filtered_savings_df['Fecha valor'].sort_values().diff().dt.days.dropna()
            avg_frequency = date_diffs.mean()
            
            if not pd.isna(avg_frequency):
                st.metric("⏱️ Average Days Between Savings", f"{avg_frequency:.0f} days")
    else:
        st.warning("🔍 No savings transactions match your search criteria.")

def render_database_info():
    """
    Render database statistics and management options.
    """
    st.subheader("📊 Database Information")
    
    # Get database statistics
    stats = st.session_state.db.get_database_stats()
    
    # Display overview metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("📈 Total Transactions", stats['total_transactions'])
    with col2:
        if stats['date_range'][0] and stats['date_range'][1]:
            st.metric("📅 Date Range", f"{stats['date_range'][0]} to {stats['date_range'][1]}")
    with col3:
        st.metric("🏷️ Categories", len(stats['category_counts']))
    
    # Category breakdown
    st.subheader("📋 Transactions by Category")
    if stats['category_counts']:
        category_df = pd.DataFrame(list(stats['category_counts'].items()), 
                                 columns=['Category', 'Count'])
        category_df = category_df.sort_values('Count', ascending=False)
        
        # Display as chart
        fig = px.bar(category_df, x='Category', y='Count', 
                    title='Transaction Count by Category',
                    color='Count',
                    color_continuous_scale='viridis')
        fig.update_layout(xaxis_tickangle=-45)
        st.plotly_chart(fig, use_container_width=True)
        
        # Display as table
        st.dataframe(category_df, use_container_width=True)
    
    # Database management
    st.subheader("🔧 Database Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.info("💾 **Database Location**: `finance_data.db`")
        st.info("🔄 **Auto-sync**: Categories and transactions are automatically synced")
    
    with col2:
        if st.button("🔄 Refresh Data", help="Reload all data from database"):
            st.session_state.all_transactions_df = st.session_state.db.load_all_transactions()
            st.success("✅ Data refreshed from database")
            st.rerun()
    
    # Recent transactions
    st.subheader("🕒 Recent Transactions")
    if not st.session_state.all_transactions_df.empty:
        recent_transactions = st.session_state.all_transactions_df.head(10)
        st.dataframe(recent_transactions, use_container_width=True)

def get_ai_analysis(debits_df, credits_df, selected_month):
    """
    Get AI analysis for the given financial data.
    
    Args:
        debits_df (pandas.DataFrame): Debit transactions
        credits_df (pandas.DataFrame): Credit transactions
        selected_month (str): Selected month filter
        
    Returns:
        tuple: (success: bool, response: str, error: str)
    """
    try:
        # Initialize OpenAI service
        ai_service = OpenAIService()
        
        # Format data for AI
        formatted_data = format_bank_statement_for_ai(debits_df, credits_df, selected_month)
        
        # Get AI analysis
        ai_response = ai_service.get_response_bank_statement(formatted_data)
        
        return True, ai_response, None
        
    except Exception as e:
        return False, None, str(e)

def render_ai_analysis_section(debits_df, credits_df, selected_month):
    """
    Render AI analysis section with automatic updates on month change.
    
    Args:
        debits_df (pandas.DataFrame): Debit transactions
        credits_df (pandas.DataFrame): Credit transactions
        selected_month (str): Selected month filter
    """
    st.markdown("---")
    st.subheader("🤖 AI Financial Analysis")
    
    # Check if we have data
    if len(debits_df) == 0:
        st.info("💡 Upload transactions to get AI insights!")
        return
    
    # Create a unique key for this month's analysis
    analysis_key = f"ai_analysis_{selected_month}_{len(debits_df)}_{len(credits_df)}"
    
    # Check if we need to update the analysis (month changed or first time)
    if "last_analysis_key" not in st.session_state or st.session_state.last_analysis_key != analysis_key:
        st.session_state.last_analysis_key = analysis_key
        st.session_state.ai_analysis_loading = True
        st.session_state.ai_analysis_result = None
        st.session_state.ai_analysis_error = None
    
    period_text = selected_month if selected_month != 'All Months' else 'All available data'
    
    # Show current period info
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("📊 Period", period_text)
    with col2:
        st.metric("💳 Transactions", f"{len(debits_df)} expenses, {len(credits_df)} income")
    
    # Auto-trigger analysis if loading state is True
    if st.session_state.get("ai_analysis_loading", False):
        with st.spinner("🧠 AI is analyzing your financial data..."):
            success, response, error = get_ai_analysis(debits_df, credits_df, selected_month)
            
            if success:
                st.session_state.ai_analysis_result = response
                st.session_state.ai_analysis_error = None
            else:
                st.session_state.ai_analysis_result = None
                st.session_state.ai_analysis_error = error
            
            st.session_state.ai_analysis_loading = False
    
    # Display results if available
    if st.session_state.get("ai_analysis_result"):
        st.success("✅ Analysis Complete!")
        
        # Create an expandable section for the analysis
        with st.expander("📈 AI Financial Insights & Recommendations", expanded=True):
            st.markdown(st.session_state.ai_analysis_result)
        
        # Add refresh button
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("🔄 Refresh Analysis", help="Get updated AI insights for this period"):
                st.session_state.ai_analysis_loading = True
                st.rerun()
    
    # Display error if any
    elif st.session_state.get("ai_analysis_error"):
        st.error(f"❌ Error during AI analysis: {st.session_state.ai_analysis_error}")
        st.info("💡 Make sure your OpenAI API key is configured correctly in the config file.")
        
        # Add retry button
        if st.button("🔄 Retry Analysis"):
            st.session_state.ai_analysis_loading = True
            st.rerun()

# ============================================================================
# MAIN APPLICATION FUNCTION
# ============================================================================

def initialize_session_state():
    """
    Initialize Streamlit session state with categories and database if not already present.
    """
    if "categories" not in st.session_state:
        st.session_state.categories = load_categories()
    
    if "db" not in st.session_state:
        st.session_state.db = FinanceDatabase()
        print("🗄️ Database connection initialized")
    
    if "all_transactions_df" not in st.session_state:
        # Load all existing transactions from database on app start
        st.session_state.all_transactions_df = st.session_state.db.load_all_transactions()
        if not st.session_state.all_transactions_df.empty:
            print(f"📊 Loaded {len(st.session_state.all_transactions_df)} existing transactions from database")

def render_app_header():
    """
    Render the modern, friendly app header with logo and branding.
    """
    st.markdown("""
    <div class="main-header">
        <div class="logo-container">
            <div class="logo">💎</div>
            <h1 class="app-title">WealthWise</h1>
        </div>
        <p class="app-subtitle">✨ Smart Personal Finance Made Simple & Beautiful ✨</p>
    </div>
    """, unsafe_allow_html=True)



def main():
    """
    Main application function that orchestrates the entire financial analysis tool.
    """
    # Load custom CSS styling
    load_custom_css()
    
    # Initialize session state
    initialize_session_state()
    
    # Render professional header
    render_app_header()
    
    # Display database statistics
    if not st.session_state.all_transactions_df.empty:
        stats = st.session_state.db.get_database_stats()
        st.info(f"📊 Database contains {stats['total_transactions']} transactions from {stats['date_range'][0]} to {stats['date_range'][1]}")
    
    # File upload section
    st.markdown("### 🚀 Let's Get Started!")
    if st.session_state.all_transactions_df.empty:
        st.markdown("**Drop your first bank statement here to get started!** ✨")
    else:
        st.markdown("**Upload new monthly statements - duplicates will be automatically skipped!** ✨")
    
    uploaded_file = st.file_uploader(
        "📊 Choose your CSV file", 
        type=["csv"],
        help="Drag & drop your bank statement CSV file here - we'll take care of the rest!"
    )
    
    # Handle file upload and database logic
    df_to_use = None
    
    if uploaded_file is not None:
        # Process uploaded file (this will show upload feedback)
        uploaded_df = load_transactions(uploaded_file)
        
        # Use all transactions from database (including any newly added)
        if not st.session_state.all_transactions_df.empty:
            df_to_use = st.session_state.all_transactions_df.copy()
        else:
            df_to_use = uploaded_df
            
    elif not st.session_state.all_transactions_df.empty:
        # No upload, but we have existing data in database
        df_to_use = st.session_state.all_transactions_df.copy()
        st.success(f"📊 Displaying all {len(df_to_use)} transactions from database")
    
    if df_to_use is not None and not df_to_use.empty:
        # Prepare monthly filtering
        df_with_months, available_months = prepare_monthly_data(df_to_use)
        
        # Month selection UI
        selected_month = render_month_selector(available_months)
        
        # Filter data by selected month
        filtered_df = filter_data_by_month(df_with_months, selected_month)
        
        # Separate debits and credits
        debits_df, credits_df = separate_debits_credits(filtered_df)
        
        # Display summary metrics
        render_summary_metrics(debits_df, credits_df)
        
        # AI Analysis Section
        render_ai_analysis_section(debits_df, credits_df, selected_month)
        
        # Store debits in session state for editing
        st.session_state.debits_df = debits_df.copy()
        
        # Create main tabs
        tab1, tab2, tab3 = st.tabs(["Debits", "Credits", "Savings"])
        
        with tab1:
            # Category management
            render_category_management()
            
            # Transaction editor
            edited_df = render_transaction_editor(st.session_state.debits_df)
            
            # Process category changes
            process_category_changes(edited_df)
            
            # Expense summary and visualization
            render_expense_summary(st.session_state.debits_df)
        
        with tab2:
            # Credits/Income display
            render_credits_tab(credits_df)
        
        with tab3:
            # Savings transactions and analysis
            render_savings_tab(debits_df)
    
    elif uploaded_file is not None:
        # Handle case where file upload failed
        st.error("❌ Failed to process the uploaded file. Please check the file format.")
    else:
        # No data available
        st.info("👆 Upload your first CSV file to get started with your financial analysis!")

if __name__ == "__main__":
    main()