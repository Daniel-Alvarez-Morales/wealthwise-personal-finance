# 💎 WealthWise - Personal Finance Tracker

**Smart Personal Finance Made Simple & Beautiful** ✨

WealthWise is a comprehensive personal finance application that helps you analyze, categorize, and track your bank transactions with the power of AI automation and beautiful visualizations.

![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)
![Streamlit](https://img.shields.io/badge/Streamlit-1.28+-red.svg)
![SQLite](https://img.shields.io/badge/SQLite-3.0+-green.svg)
![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-orange.svg)

## 🚀 Features

### 📊 **Transaction Management**
- **CSV Upload**: Import bank statements in CSV format
- **Duplicate Detection**: Automatic detection and skipping of duplicate transactions
- **Monthly Filtering**: View transactions by specific months or all data
- **Search Functionality**: Search transactions by description (Concepto)
- **Persistent Storage**: All data stored in local SQLite database

### 🤖 **AI-Powered Categorization**
- **Smart Categorization**: AI analyzes transaction descriptions and suggests categories
- **Keyword Extraction**: Automatically extracts meaningful merchant names and service types
- **Confidence-Based**: Only categorizes transactions with >80% confidence
- **Manual Override**: Easy manual categorization for edge cases

### 📈 **Analytics & Visualization**
- **Financial Metrics**: Income, expenses, and balance tracking
- **Category Breakdown**: Pie charts and tables showing spending by category
- **Monthly Analysis**: Filter and analyze data by specific time periods
- **AI Financial Insights**: Get personalized financial analysis and recommendations

### 🎨 **Modern UI/UX**
- **Professional Design**: Clean, modern interface with custom CSS styling
- **Responsive Layout**: Works on desktop and mobile devices
- **Interactive Tables**: Edit categories directly in the interface
- **Real-time Updates**: Instant feedback and data synchronization

## 🛠️ Tech Stack

### **Frontend**
- **[Streamlit](https://streamlit.io/)** - Web application framework
- **[Plotly](https://plotly.com/python/)** - Interactive data visualizations
- **Custom CSS** - Professional styling and theming

### **Backend**
- **[Python 3.8+](https://python.org/)** - Core programming language
- **[Pandas](https://pandas.pydata.org/)** - Data manipulation and analysis
- **[SQLite](https://sqlite.org/)** - Local database for persistent storage
- **[OpenAI API](https://openai.com/)** - AI-powered transaction categorization

### **Data Processing**
- **CSV Parsing** - Bank statement import and processing
- **Transaction Hashing** - SHA-256 based duplicate detection
- **Date Processing** - Automatic date parsing and formatting
- **Currency Handling** - Euro symbol and decimal separator processing

## 📋 Prerequisites

- Python 3.8 or higher
- OpenAI API key (for AI categorization features)

## 🚀 Installation

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd personal_finance
   ```

2. **Install dependencies**
   ```bash
   pip install streamlit pandas plotly openai
   ```

3. **Create configuration file**
   ```bash
   # Create config.py with your OpenAI API key
   echo "OPENAI_API_KEY = 'your-api-key-here'" > config.py
   ```

4. **Run the application**
   ```bash
   streamlit run main.py
   ```

## 📖 How to Use

### **First Time Setup**

1. **Launch the App**: Run `streamlit run main.py`
2. **Upload CSV**: Drop your bank statement CSV file
3. **Review Categories**: Check the automatic categorization
4. **Use AI Categorization**: Click "🤖 AI Categorize" for uncategorized transactions

### **Monthly Updates**

1. **Upload New Statement**: Drop your new monthly CSV file
2. **Automatic Processing**: App detects and skips duplicate transactions
3. **View Results**: See how many new vs duplicate transactions were processed
4. **Analyze Data**: Use filters and search to explore your financial data

### **Managing Categories**

- **Add Categories**: Use the "New Category" input to create custom categories
- **Edit Transactions**: Click on category cells in the table to change categorization
- **Search & Filter**: Use the search box to find specific transactions
- **AI Assistance**: Let AI suggest categories for uncategorized transactions

## 🗄️ Database Schema

### **Transactions Table**
```sql
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_hash TEXT UNIQUE NOT NULL,
    fecha_valor DATE NOT NULL,
    concepto TEXT NOT NULL,
    importe REAL NOT NULL,
    tipo TEXT NOT NULL,
    category TEXT NOT NULL,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### **Categories Table**
```sql
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category_name TEXT UNIQUE NOT NULL,
    keywords TEXT NOT NULL,
    created_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_modified TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## 🔧 Implementation Details

### **Duplicate Detection**
- Uses SHA-256 hash of `(date + concept + amount)` for unique transaction identification
- Automatically skips duplicate transactions during CSV upload
- Provides clear feedback on new vs duplicate transaction counts

### **Category Management**
- **JSON Storage**: Categories stored in `categories.json` for easy editing
- **Database Sync**: Categories automatically synchronized with SQLite database
- **Keyword Matching**: Case-insensitive substring matching for transaction categorization
- **AI Enhancement**: OpenAI GPT-4 analyzes uncategorized transactions and suggests keywords

### **Data Processing Pipeline**
1. **CSV Upload** → Parse and validate data
2. **Data Cleaning** → Handle currency symbols, decimal separators
3. **Transaction Typing** → Classify as Debit/Credit, convert to positive amounts
4. **Categorization** → Match against existing keywords
5. **Database Storage** → Store with duplicate detection
6. **AI Analysis** → Optional AI categorization for uncategorized items

### **Security & Privacy**
- **Local Storage**: All data stored locally in SQLite database
- **No Data Transmission**: Financial data never leaves your machine (except OpenAI API calls for categorization)
- **API Key Protection**: Configuration file excluded from version control
- **Sensitive Data Exclusion**: `.gitignore` protects personal financial data

## 📁 File Structure

```
personal_finance/
├── main.py                 # Main Streamlit application
├── database.py             # Database operations and models
├── open_ai_service.py      # OpenAI API integration
├── styles.css              # Custom CSS styling
├── categories.json         # Category definitions (auto-generated)
├── finance_data.db         # SQLite database (auto-generated)
├── config.py               # Configuration (create manually)
├── .gitignore              # Git ignore rules
└── README.md               # This file
```

## 🎯 CSV Format Requirements

Your bank statement CSV should have these columns:
- **Fecha valor**: Transaction date (DD/MM/YYYY format)
- **Concepto**: Transaction description
- **Importe**: Amount (supports €, commas as decimal separators)
- **Divisa**: Currency (optional)

Example:
```csv
Fecha valor,Concepto,Importe,Divisa
15/08/2024,"PAGO MOVIL EN MERCADONA","-25,50",EUR
12/08/2024,"TRANSFERENCIA NOMINA","2.500,00",EUR
```

## 🤖 AI Features

### **Smart Categorization**
- Analyzes transaction descriptions using OpenAI GPT-4
- Extracts meaningful keywords (merchant names, service types)
- Ignores transaction IDs, amounts, and variable details
- Only suggests categories with >80% confidence

### **Financial Analysis**
- Provides personalized insights based on spending patterns
- Identifies trends and offers financial tips
- Analyzes income vs expenses across different time periods

## 🔮 Future Enhancements

- [ ] **Multi-currency Support**: Handle different currencies automatically
- [ ] **Budget Planning**: Set and track monthly budgets by category
- [ ] **Export Features**: Export data to Excel, PDF reports
- [ ] **Mobile App**: React Native mobile application
- [ ] **Bank Integration**: Direct bank API connections
- [ ] **Advanced Analytics**: Predictive spending analysis

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Streamlit** - For the amazing web app framework
- **OpenAI** - For powerful AI categorization capabilities
- **Plotly** - For beautiful interactive visualizations
- **Pandas** - For robust data manipulation tools

---

**Made with ❤️ for better financial management**

*WealthWise - Smart Personal Finance Made Simple & Beautiful* ✨
