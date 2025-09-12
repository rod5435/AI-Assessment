# 🧠 Multi-Industry AI Assessment Platform

A Flask-based web application to assess companies across multiple industries (Government Contracting, Healthcare, Finance, and Industrial) on their AI capabilities, strategies, and technical maturity. This tool allows users to track and score AI readiness across multiple companies and export reports for decision-making.

## 🚀 Features

### 📊 **Enhanced Company Dashboard (Home Page)**
- **Sortable Table Layout**: Clean 4-column table with Company Name, Annual Revenue, Number of Employees, and Overall Score
- **Interactive Sorting**: Click any column header to sort ascending/descending with visual indicators (↕, ↑, ↓)
- **Company Name Links**: Hyperlinks to detailed assessment pages
- **Color-Coded Score Badges**: Red (1-3), Yellow (4-6), Green (7-10), Gray (No Score)
- **Statistics Overview**: Total Companies, Scored Companies, Average Score, Pending Scoring
- **Responsive Design**: Table scrolls horizontally on smaller screens

### 🔍 **Advanced Company Assessment Page**
- **Left Panel Navigation**: Section buttons with real-time score display
- **Smart Section Highlighting**: Only one section highlighted at a time
- **Auto-Score Updates**: Scores recalculate automatically when switching sections or editing answers
- **Enhanced Text Areas**: Auto-save on blur and after 1 second of inactivity
- **Visual Feedback**: Border color changes during saving/scoring process
- **Section Score Sync**: Left panel and main content scores stay synchronized

### 📂 **Enhanced Data Management**
- **Smart CSV Upload with Confirmation**: 
  - Loading overlay with progress indication
  - Prevents multiple submissions during upload
  - **Company Existence Check**: Warns user if company already exists
  - **Confirmation Modal**: Clear choice to replace existing data or cancel
  - Automatic AI scoring on successful upload
  - Better error handling and user feedback
- **Enhanced Company Data**: 
  - **Annual Revenue Extraction**: Automatically extracts from CSV
  - **Employee Count Extraction**: Automatically extracts from CSV
  - **Dashboard Display**: Shows revenue and employee data in main table
- **Smart Company Detection**: Automatically generates company names from filenames for synthetic data
- **Download Report**: Export comprehensive PDF reports for any company
- **Download Template**: Get the standard assessment template

### 📋 **Enhanced Get-Well Plans Summary**
- **Current Section Scores**: Shows AI-generated scores for each section alongside plans
- **Visual Priority Indicators**: 
  - Red background for sections scoring 1-3 (Needs Attention)
  - Yellow background for sections scoring 4-6 (Room for Improvement)
  - White background for sections scoring 7-10 (Good)
- **Comprehensive Statistics**: Total Plans, Completed Plans, Pending Plans, Overall Score
- **Status Messages**: Plan availability and improvement priority indicators
- **Future Readiness Handling**: Properly excluded from scoring with "No Scoring" display

### 🤖 **Intelligent AI-Powered Scoring**
- **OpenAI GPT-4o-mini Integration**: Advanced AI analysis for accurate scoring
- **Section-Specific Prompts**: Custom evaluation criteria for each assessment area
- **Real-Time Updates**: Automatic score recalculation on answer changes
- **Future Readiness Exclusion**: Section 6 properly excluded from overall scoring (future-focused)
- **Enhanced Error Handling**: Graceful fallbacks for API failures

### 🎯 **Smart Scoring Logic**
- **Section Scores**: AI-generated 1-10 scores based on comprehensive analysis
- **Overall Score**: Average of Sections 1-5 only (excludes Future Readiness)
- **Visual Status Indicators**:
  - 🔴 1–3 → Red (Needs Improvement)
  - 🟡 4–6 → Yellow (Room for Improvement) 
  - 🟢 7–10 → Green (Good/Excellent)
  - ⚪ No Score → Gray (Pending AI Scoring)

## 🛠️ Installation & Setup

### Prerequisites
- Python 3.8 or higher
- OpenAI API key

### 1. Clone the Repository
```bash
git clone <repository-url>
cd AI-Assessment
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Environment Setup
Create a `.env` file in the root directory:
```bash
# Flask Configuration
SECRET_KEY=your-secret-key-change-in-production
FLASK_ENV=development

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here

# Database Configuration
DATABASE_URL=sqlite:///govcon_ai_assessments.db
```

### 4. Run the Application
```bash
python run.py
```

The application will be available at `http://localhost:5010`

## 📊 Usage

### Getting Started
1. **Access the Dashboard**: Visit `http://localhost:5010`
2. **Upload Assessment**: Click "Upload New Assessment" to add company data
3. **View Details**: Click on any company name to see detailed assessments
4. **Edit Responses**: Modify answers in real-time with auto-save
5. **Generate Reports**: Download PDF reports for any company
6. **Review Get-Well Plans**: Access improvement strategies with current scores

### CSV Upload Process
1. **Select File**: Choose a CSV file with assessment data
2. **Company Check**: System checks if company already exists
3. **Confirmation (if needed)**: Modal appears if company exists, user chooses to replace or cancel
4. **Processing**: Loading overlay shows upload progress
5. **Data Extraction**: Annual Revenue and Employee Count automatically extracted
6. **Automatic Scoring**: AI scores are calculated immediately after upload
7. **Success**: Redirected to company detail page with all scores

### CSV Upload Format
The application expects CSV files with the following structure:
```csv
Section,Question,Answer
Section 1: Company Profile & Strategic Alignment,Company Name,Acme Corporation
Section 1: Company Profile & Strategic Alignment,Annual Revenue,$25M - $50M
Section 1: Company Profile & Strategic Alignment,Number of Employees,150-300
Section 1: Company Profile & Strategic Alignment,Primary NAICS Codes,541330
...
```

**Required Fields:**
- **Company Name**: Must be in Section 1
- **Annual Revenue**: Automatically extracted and displayed on dashboard
- **Number of Employees**: Automatically extracted and displayed on dashboard

### Assessment Sections
1. **Company Profile & Strategic Alignment**: Strategic clarity, executive sponsorship, AI roadmap, investment approach
2. **AI Capabilities & Technical Maturity**: AI/ML capabilities, talent, tooling, lifecycle practices, personal AI usage
3. **Industry-Specific Section 3** (varies by company type):
   - **Government Contracting**: Government AI Integration & Contract Performance
   - **Healthcare**: AI Adoption & Compliance in Healthcare Settings  
   - **Finance**: AI Integration & Financial Services Delivery
4. **Partnerships, Ecosystem & Industry Engagement**: Cloud partnerships, academic collaboration, industry partnerships
5. **AI Talent, Culture & Organizational Readiness**: AI roles, training, ethics, internal AI usage, business development integration
6. **Future Readiness & Differentiators**: Emerging AI capabilities, competitive advantages, scaling challenges *(Not scored)*

## 🧠 Enhanced Scoring System

### **AI-Powered Analysis**
- **Section-Specific Prompts**: Each section uses custom evaluation criteria
- **Comprehensive Analysis**: AI considers multiple factors for accurate scoring
- **Real-Time Processing**: Scores update immediately as answers change
- **Quality Assurance**: Multiple validation layers ensure scoring accuracy

### **Scoring Logic**
- **Section Scores**: 1-10 scale based on AI analysis of all questions in section
- **Overall Score**: Average of Sections 1-5 only (excludes Future Readiness)
- **Future Readiness**: Displayed but not scored (future-focused planning)
- **Visual Indicators**: Color-coded badges for quick assessment

### **Score Categories**
- **🔴 1–3 (Red)**: Needs significant improvement
- **🟡 4–6 (Yellow)**: Room for improvement
- **🟢 7–10 (Green)**: Good to excellent performance
- **⚪ No Score (Gray)**: Pending AI scoring

## 📁 Project Structure

```
AI Assessment/
├── app.py                 # Main Flask application with enhanced features
├── config.py             # OpenAI prompts configuration
├── run.py                # Application runner (port 5010)
├── requirements.txt      # Python dependencies
├── upload_csv_to_sqlite.py  # CSV upload utility
├── templates/            # HTML templates
│   ├── base.html         # Base template with enhanced styling
│   ├── index.html        # Enhanced dashboard with sortable table
│   ├── company_detail.html  # Advanced assessment details with auto-scoring
│   ├── upload_csv.html   # Enhanced CSV upload with loading overlay
│   └── getwell_plans.html  # Enhanced Get-Well Plans with section scores
├── Data/                 # Sample assessment data
│   ├── company_1_assessment.csv
│   ├── company_2_assessment.csv
│   └── ...
└── uploads/              # Temporary file storage
```

## 🔧 Configuration

### OpenAI Prompts
The `config.py` file contains section-specific prompts for AI scoring. Each section has a custom prompt that evaluates different aspects of AI readiness.

### Database
The application uses SQLite by default. The database file (`govcon_ai_assessments.db`) will be created automatically on first run.

## 📄 API Endpoints

- `GET /` - Enhanced company dashboard with sortable table
- `GET /company/<id>` - Advanced company assessment details
- `POST /api/update_assessment` - Update assessment answers with auto-scoring
- `GET /upload_csv` - Enhanced CSV upload page
- `POST /upload_csv` - Process uploaded CSV with loading overlay
- `GET /getwell_plans/<id>` - Enhanced Get-Well Plans with section scores
- `GET /download_report/<id>` - Download PDF report
- `GET /download_template` - Download CSV template

## 🚀 Deployment

### Production Setup
1. Set `FLASK_ENV=production`
2. Use a proper `SECRET_KEY`
3. Configure a production database (PostgreSQL recommended)
4. Set up a reverse proxy (nginx)
5. Use a WSGI server (gunicorn)

### Docker Deployment
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5010
CMD ["gunicorn", "--bind", "0.0.0.0:5010", "app:app"]
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For support and questions:
- Check the documentation
- Review the code comments
- Open an issue on GitHub

## 🔮 Roadmap

- [x] Enhanced table-based dashboard with sorting
- [x] Real-time auto-scoring with AI
- [x] Loading indicators for better UX
- [x] Enhanced Get-Well Plans with section scores
- [x] Future Readiness exclusion from scoring
- [x] Improved error handling and user feedback
- [ ] AI-based analysis of free-text responses
- [ ] Scoring model customization per user/org
- [ ] Advanced analytics and benchmarking
- [ ] Integration with government databases
- [ ] Mobile-responsive design improvements
- [ ] Multi-user authentication and roles
- [ ] API for external integrations

## 🎉 Recent Updates

### Version 2.0.0 - Multi-Industry AI Assessment Platform
- **Industry-Specific Assessments**: Support for Government Contracting, Healthcare, Finance, and Industrial companies
- **Dynamic Section 3**: Industry-specific questions and scoring based on company type
- **Enhanced Company Profile**: Added Company Type and NAICS Codes fields
- **Updated Scoring Prompts**: Industry-specific AI evaluation criteria for each sector
- **Comprehensive Template**: New questionnaire structure with industry-specific questions
- **Sample Data**: Updated sample data for all supported industries

### Version 1.7.0 - Smart Data Management & Company Information
- **Smart Upload Confirmation**: Modal confirmation when replacing existing company data
- **Enhanced Company Data**: Automatic extraction of Annual Revenue and Employee Count from CSV
- **Dashboard Enhancement**: Revenue and employee data displayed in main table
- **Data Safety**: Prevents accidental data loss with clear user choice
- **Improved CSV Processing**: Better handling of company information extraction

### Version 1.6.0 - Enhanced User Experience
- **Sortable Dashboard**: Interactive table with column sorting
- **Auto-Scoring**: Real-time AI score updates on answer changes
- **Loading States**: Professional loading overlays for uploads
- **Enhanced Get-Well Plans**: Section scores and priority indicators
- **Smart Scoring**: Future Readiness properly excluded from calculations
- **Improved UX**: Better visual feedback and error handling 