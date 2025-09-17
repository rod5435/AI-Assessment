from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, send_file
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import secure_filename
import os
import pandas as pd
import sqlite3
import json
from datetime import datetime
import openai
from dotenv import load_dotenv
import config
import markdown

# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///govcon_ai_assessments.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Initialize database
db = SQLAlchemy(app)

# Configure OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

# Add custom Jinja2 filter for markdown conversion
@app.template_filter('markdown')
def markdown_filter(text):
    """Convert markdown text to HTML"""
    if not text:
        return ''
    return markdown.markdown(text, extensions=['nl2br', 'fenced_code'])

# Add markdown function to template context
@app.context_processor
def utility_processor():
    def markdown_to_html(text):
        if not text:
            return ''
        return markdown.markdown(text, extensions=['nl2br', 'fenced_code'])
    return dict(markdown_to_html=markdown_to_html)

# Database Models
class Company(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    annual_revenue = db.Column(db.String(100))
    employee_count = db.Column(db.String(100))
    company_type = db.Column(db.String(100))  # Basic, FS/FTS, Healthcare, T&G (or legacy: GovCon, Healthcare, Finance, Industrial)
    naics_codes = db.Column(db.String(200))   # Primary NAICS Codes
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to assessments
    assessments = db.relationship('Assessment', backref='company', lazy=True, cascade='all, delete-orphan')
    getwell_plans = db.relationship('GetWellPlan', backref='company', lazy=True, cascade='all, delete-orphan')

class Assessment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    section = db.Column(db.String(200), nullable=False)
    question = db.Column(db.Text, nullable=False)
    answer = db.Column(db.Text)
    score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class GetWellPlan(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    section = db.Column(db.String(200), nullable=False)
    plan_text = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Create database tables
with app.app_context():
    db.create_all()

def get_section_score(company_id, section):
    """Calculate average score for a section"""
    assessments = Assessment.query.filter_by(company_id=company_id, section=section).all()
    scored_assessments = [a for a in assessments if a.score is not None]
    
    if not scored_assessments:
        return None
    
    return sum(a.score for a in scored_assessments) / len(scored_assessments)

def get_company_sections(company_id):
    """Get the appropriate sections for a company based on its type"""
    company = Company.query.get(company_id)
    if not company:
        return []
    
    base_sections = [
        'Section 1: Company Profile & Strategic Alignment',
        'Section 2: AI Capabilities & Technical Maturity',
        'Section 4: Partnerships, Ecosystem & Industry Engagement',
        'Section 5: AI Talent, Culture & Organizational Readiness'
    ]
    
    # Add industry-specific Section 3
    if company.company_type == 'Healthcare':
        base_sections.insert(2, 'Section 3: AI Adoption & Compliance in Healthcare Settings')
    elif company.company_type in ['Finance', 'FS', 'FTS', 'Financial Transaction Services']:
        base_sections.insert(2, 'Section 3: AI Integration & Financial Services Delivery')
    elif company.company_type in ['Technology & Government', 'T&G']:
        base_sections.insert(2, 'Section 3: Government AI Integration & Contract Performance')
    elif company.company_type == 'Basic':
        base_sections.insert(2, 'Section 3: AI Integration & Business Operations')
    else:  # Default to GovCon for backward compatibility
        base_sections.insert(2, 'Section 3: Government AI Integration & Contract Performance')
    
    return base_sections

def get_overall_score(company_id):
    """Calculate overall score for a company (excluding Future Readiness)"""
    sections = get_company_sections(company_id)
    
    section_scores = []
    for section in sections:
        score = get_section_score(company_id, section)
        if score is not None:
            section_scores.append(score)
    
    if not section_scores:
        return None
    
    return sum(section_scores) / len(section_scores)

def get_score_color(score):
    """Get color class based on score"""
    if score is None:
        return 'gray'
    elif score <= 3:
        return 'red'
    elif score <= 6:
        return 'yellow'
    else:
        return 'green'

def generate_ai_score(section, responses):
    """Generate AI score using OpenAI"""
    try:
        # Get the appropriate prompt from config
        section_prompts = {
            'Section 1: Company Profile & Strategic Alignment': config.SECTION_1_PROMPT,
            'Section 2: AI Capabilities & Technical Maturity': config.SECTION_2_PROMPT,
            'Section 3: Government AI Integration & Contract Performance': config.SECTION_3_GOVCON_PROMPT,
            'Section 3: AI Adoption & Compliance in Healthcare Settings': config.SECTION_3_HEALTHCARE_PROMPT,
            'Section 3: AI Integration & Financial Services Delivery': config.SECTION_3_FINANCE_PROMPT,
            'Section 4: Partnerships, Ecosystem & Industry Engagement': config.SECTION_4_PROMPT,
            'Section 5: AI Talent, Culture & Organizational Readiness': config.SECTION_5_PROMPT,
            'Section 6: Future Readiness & Differentiators': config.SECTION_6_PROMPT
        }
        
        prompt_config = section_prompts.get(section)
        if not prompt_config:
            return None
        
        # Format responses for the prompt
        formatted_responses = "\n".join([f"Q: {q}\nA: {a}" for q, a in responses])
        prompt = prompt_config['prompt'].replace('{{responses}}', formatted_responses)
        
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an AI assessment expert. Provide only a JSON response with 'score' (integer 1-10) and 'justification' (string)."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        
        # Parse the response
        content = response.choices[0].message.content
        try:
            # Try to extract JSON from the response
            if '{' in content and '}' in content:
                json_start = content.find('{')
                json_end = content.rfind('}') + 1
                json_str = content[json_start:json_end]
                result = json.loads(json_str)
                return result.get('score')
        except:
            # If JSON parsing fails, try to extract score from text
            import re
            score_match = re.search(r'\b(\d+)\b', content)
            if score_match:
                score = int(score_match.group(1))
                return max(1, min(10, score))  # Ensure score is between 1-10
        
        return None
    except Exception as e:
        print(f"Error generating AI score: {e}")
        return None

def generate_ai_getwell_plan(section, responses, score, company_type):
    """Generate AI Get-Well Plan using OpenAI"""
    try:
        # Get the appropriate prompt from config
        getwell_prompts = {
            'Section 1: Company Profile & Strategic Alignment': config.GETWELL_SECTION_1_PROMPT,
            'Section 2: AI Capabilities & Technical Maturity': config.GETWELL_SECTION_2_PROMPT,
            'Section 3: Government AI Integration & Contract Performance': config.GETWELL_SECTION_3_GOVCON_PROMPT,
            'Section 3: AI Adoption & Compliance in Healthcare Settings': config.GETWELL_SECTION_3_HEALTHCARE_PROMPT,
            'Section 3: AI Integration & Financial Services Delivery': config.GETWELL_SECTION_3_FINANCE_PROMPT,
            'Section 4: Partnerships, Ecosystem & Industry Engagement': config.GETWELL_SECTION_4_PROMPT,
            'Section 5: AI Talent, Culture & Organizational Readiness': config.GETWELL_SECTION_5_PROMPT,
            'Section 6: Future Readiness & Differentiators': config.GETWELL_SECTION_6_PROMPT
        }
        
        prompt_config = getwell_prompts.get(section)
        if not prompt_config:
            return None
        
        # Format responses for the prompt
        formatted_responses = "\n".join([f"Q: {q}\nA: {a}" for q, a in responses])
        
        # Replace placeholders in the prompt
        prompt = prompt_config['prompt'].replace('{{responses}}', formatted_responses)
        prompt = prompt.replace('{{score}}', str(score))
        prompt = prompt.replace('{{company_type}}', company_type or 'Unknown')
        
        response = openai.ChatCompletion.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert AI consultant specializing in strategic planning and organizational development. Provide comprehensive, actionable Get-Well Plans with specific recommendations, timelines, and success metrics."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=1500
        )
        
        # Return the generated Get-Well Plan
        return response.choices[0].message.content.strip()
        
    except Exception as e:
        print(f"Error generating AI Get-Well Plan: {e}")
        return None

def calculate_all_section_scores(company_id):
    """Calculate AI scores for all sections of a company (excluding Future Readiness)"""
    sections = get_company_sections(company_id)
    
    # Get company information for Get-Well Plan generation
    company = Company.query.get(company_id)
    company_type = company.company_type if company else None
    
    results = {}
    
    for section in sections:
        print(f"Calculating score for {section}...")
        
        # Get all assessments for this section
        assessments = Assessment.query.filter_by(company_id=company_id, section=section).all()
        
        # Filter out Get-Well Plan questions and empty answers
        responses = [(a.question, a.answer) for a in assessments 
                    if a.answer and 'Get-Well Plan' not in a.question and a.answer.strip()]
        
        if responses:
            # Generate AI score
            score = generate_ai_score(section, responses)
            if score is not None:
                # Update all assessments in this section with the new score
                for a in assessments:
                    if 'Get-Well Plan' not in a.question:
                        a.score = score
                
                # Generate AI Get-Well Plan
                print(f"  Generating Get-Well Plan for {section}...")
                getwell_plan = generate_ai_getwell_plan(section, responses, score, company_type)
                
                if getwell_plan:
                    # Update or create Get-Well Plan
                    existing_plan = GetWellPlan.query.filter_by(
                        company_id=company_id, 
                        section=section
                    ).first()
                    
                    if existing_plan:
                        existing_plan.plan_text = getwell_plan
                    else:
                        new_plan = GetWellPlan(
                            company_id=company_id,
                            section=section,
                            plan_text=getwell_plan
                        )
                        db.session.add(new_plan)
                    
                    print(f"  Get-Well Plan generated successfully")
                else:
                    print(f"  Failed to generate Get-Well Plan")
                
                results[section] = score
                print(f"  Score: {score}/10")
            else:
                print(f"  Failed to generate score")
        else:
            print(f"  No valid responses found")
    
    # Commit all changes
    db.session.commit()
    
    return results

# Routes
@app.route('/')
def index():
    """Home page - Company Dashboard"""
    companies = Company.query.all()
    
    print(f"DEBUG: Found {len(companies)} companies in database")
    
    # Calculate scores for each company
    for company in companies:
        company.overall_score = get_overall_score(company.id)
        company.score_color = get_score_color(company.overall_score)
        
        # Get assessment count for this company
        assessment_count = Assessment.query.filter_by(company_id=company.id).count()
        company.assessment_count = assessment_count
        
        print(f"DEBUG: {company.name} - Score: {company.overall_score}, Color: {company.score_color}, Assessments: {assessment_count}")
    
    print(f"DEBUG: Passing {len(companies)} companies to template")
    return render_template('index.html', companies=companies)

@app.route('/company/<int:company_id>')
def company_detail(company_id):
    """Detailed company assessment page"""
    company = Company.query.get_or_404(company_id)
    sections = get_company_sections(company_id) + ['Section 6: Future Readiness & Differentiators']
    
    # Get assessments for each section
    section_data = {}
    for section in sections:
        assessments = Assessment.query.filter_by(company_id=company_id, section=section).all()
        section_score = get_section_score(company_id, section)
        section_data[section] = {
            'assessments': assessments,
            'score': section_score,
            'color': get_score_color(section_score)
        }
    
    # Get Get-Well Plans
    getwell_plans = GetWellPlan.query.filter_by(company_id=company_id).all()
    getwell_plans_dict = {plan.section: plan for plan in getwell_plans}
    
    # Get overall score
    overall_score = get_overall_score(company_id)
    
    return render_template('company_detail.html', 
                         company=company, 
                         sections=sections, 
                         section_data=section_data,
                         getwell_plans_dict=getwell_plans_dict,
                         overall_score=overall_score,
                         overall_color=get_score_color(overall_score))

@app.route('/api/update_assessment', methods=['POST'])
def update_assessment():
    """Update assessment answer and automatically recalculate section score"""
    data = request.get_json()
    assessment_id = data.get('assessment_id')
    answer = data.get('answer')
    
    assessment = Assessment.query.get_or_404(assessment_id)
    assessment.answer = answer
    
    # Get all responses for this section to generate AI score
    section_assessments = Assessment.query.filter_by(
        company_id=assessment.company_id, 
        section=assessment.section
    ).all()
    
    # Filter out Get-Well Plan questions and empty answers
    responses = [(a.question, a.answer) for a in section_assessments 
                if a.answer and 'Get-Well Plan' not in a.question and a.answer.strip()]
    
    if responses:
        # Generate new AI score for this section
        new_score = generate_ai_score(assessment.section, responses)
        if new_score is not None:
            # Update all assessments in this section with the new score
            for a in section_assessments:
                if 'Get-Well Plan' not in a.question:
                    a.score = new_score
            
            # Generate new AI Get-Well Plan
            company = Company.query.get(assessment.company_id)
            company_type = company.company_type if company else None
            
            print(f"Generating Get-Well Plan for {assessment.section}...")
            getwell_plan = generate_ai_getwell_plan(assessment.section, responses, new_score, company_type)
            
            if getwell_plan:
                # Update or create Get-Well Plan
                existing_plan = GetWellPlan.query.filter_by(
                    company_id=assessment.company_id, 
                    section=assessment.section
                ).first()
                
                if existing_plan:
                    existing_plan.plan_text = getwell_plan
                else:
                    new_plan = GetWellPlan(
                        company_id=assessment.company_id,
                        section=assessment.section,
                        plan_text=getwell_plan
                    )
                    db.session.add(new_plan)
                
                print(f"Get-Well Plan updated successfully")
            else:
                print(f"Failed to generate Get-Well Plan")
            
            print(f"Updated {assessment.section} score to {new_score}/10")
        else:
            print(f"Failed to generate score for {assessment.section}")
    
    db.session.commit()
    
    # Return updated scores
    section_score = get_section_score(assessment.company_id, assessment.section)
    overall_score = get_overall_score(assessment.company_id)
    
    return jsonify({
        'section_score': section_score,
        'section_color': get_score_color(section_score),
        'section_name': assessment.section,
        'overall_score': overall_score,
        'overall_color': get_score_color(overall_score)
    })

@app.route('/upload_csv', methods=['GET', 'POST'])
def upload_csv():
    """Upload CSV file to populate assessments"""
    if request.method == 'POST':
        print(f"DEBUG: Request files: {request.files}")
        print(f"DEBUG: Request form: {request.form}")
        
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        print(f"DEBUG: File object: {file}")
        print(f"DEBUG: File filename: {file.filename}")
        
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and file.filename.endswith('.csv'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                # Process the CSV file
                df = pd.read_csv(filepath)
                
                # Extract company name
                company_name_row = df[df['Question'] == 'Company Name']
                if company_name_row.empty:
                    flash('Company Name not found in CSV', 'error')
                    return redirect(request.url)
                
                company_name = company_name_row.iloc[0]['Answer']
                
                # Extract company profile information
                annual_revenue = None
                employee_count = None
                company_type = None
                naics_codes = None
                
                revenue_row = df[df['Question'] == 'Revenue']
                if not revenue_row.empty:
                    annual_revenue = revenue_row.iloc[0]['Answer']
                
                employees_row = df[df['Question'] == 'Number of Employees']
                if not employees_row.empty:
                    employee_count = employees_row.iloc[0]['Answer']
                
                # Handle both old and new Company Type question formats
                company_type_row = df[df['Question'] == 'Company Type: GovCon Healthcare Finance or Industrial']
                if company_type_row.empty:
                    company_type_row = df[df['Question'] == 'Company Type: Basic, Financial Transaction Services, Healthcare, Technology & Government']
                
                if not company_type_row.empty:
                    company_type = company_type_row.iloc[0]['Answer']
                
                naics_row = df[df['Question'] == 'Primary NAICS Codes (Only GovCon)']
                if not naics_row.empty:
                    naics_codes = naics_row.iloc[0]['Answer']
                
                # Check if the company name looks like synthetic data (contains generic AI text)
                synthetic_indicators = [
                    'Our internal R&D team',
                    'We partner with AWS',
                    'Minimal progress on model management',
                    'We lack structured AI governance',
                    'We plan to double our AI staff',
                    'We are actively expanding'
                ]
                
                is_synthetic = any(indicator in company_name for indicator in synthetic_indicators)
                
                if is_synthetic:
                    # Generate company name from filename
                    base_filename = os.path.splitext(filename)[0]
                    if 'company_' in base_filename:
                        company_num = base_filename.split('_')[1]
                        company_name = f"Company {company_num}"
                    else:
                        company_name = base_filename.replace('_', ' ').title()
                    
                    print(f"DEBUG: Generated company name '{company_name}' from filename '{filename}'")
                
                # Check if company already exists
                company = Company.query.filter_by(name=company_name).first()
                
                # Check if this is a confirmation request
                confirmed = request.form.get('confirmed') == 'true'
                
                if company and not confirmed:
                    # Company exists but no confirmation - return special response
                    return f'COMPANY_EXISTS:{company_name}', 200
                
                if not company:
                    company = Company(name=company_name)
                    db.session.add(company)
                    db.session.flush()  # Get the ID
                
                # Update company with profile data
                if annual_revenue:
                    company.annual_revenue = annual_revenue
                if employee_count:
                    company.employee_count = employee_count
                if company_type:
                    company.company_type = company_type
                if naics_codes:
                    company.naics_codes = naics_codes
                
                # Clear existing assessments for this company
                Assessment.query.filter_by(company_id=company.id).delete()
                GetWellPlan.query.filter_by(company_id=company.id).delete()
                
                # Insert new assessments
                for _, row in df.iterrows():
                    if 'Get-Well Plan' in row['Question']:
                        # Handle Get-Well Plan
                        getwell_plan = GetWellPlan(
                            company_id=company.id,
                            section=row['Section'],
                            plan_text=row['Answer']
                        )
                        db.session.add(getwell_plan)
                    else:
                        # Handle regular assessment
                        assessment = Assessment(
                            company_id=company.id,
                            section=row['Section'],
                            question=row['Question'],
                            answer=row['Answer']
                        )
                        db.session.add(assessment)
                
                db.session.commit()
                
                # Clean up uploaded file
                os.remove(filepath)
                
                # Automatically calculate AI scores for all sections
                try:
                    print(f"Automatically calculating scores for {company_name}...")
                    results = calculate_all_section_scores(company.id)
                    if results:
                        flash(f'Successfully uploaded data for {company_name} and calculated AI scores for {len(results)} sections', 'success')
                    else:
                        print(f"WARNING: No scores calculated for {company_name}. Results: {results}")
                        flash(f'Successfully uploaded data for {company_name}. Note: AI scores could not be calculated - you can manually calculate scores from the company detail page.', 'warning')
                except Exception as e:
                    print(f"ERROR: Failed to calculate scores for {company_name}: {str(e)}")
                    flash(f'Successfully uploaded data for {company_name}. Warning: Error calculating AI scores: {str(e)}. You can manually calculate scores from the company detail page.', 'warning')
                
                return redirect(url_for('company_detail', company_id=company.id))
                
            except Exception as e:
                flash(f'Error processing CSV: {str(e)}', 'error')
                return redirect(request.url)
        else:
            flash('Please upload a CSV file', 'error')
            return redirect(request.url)
    
    return render_template('upload_csv.html')

@app.route('/getwell_plans/<int:company_id>')
def getwell_plans(company_id):
    """View all Get-Well Plans for a company"""
    company = Company.query.get_or_404(company_id)
    plans = GetWellPlan.query.filter_by(company_id=company_id).all()
    
    # Get section scores for each plan
    section_scores = {}
    for plan in plans:
        if 'Future Readiness' not in plan.section:
            score = get_section_score(company_id, plan.section)
            section_scores[plan.section] = {
                'score': score,
                'color': get_score_color(score)
            }
        else:
            section_scores[plan.section] = {
                'score': None,
                'color': 'gray'
            }
    
    # Get overall score
    overall_score = get_overall_score(company_id)
    overall_color = get_score_color(overall_score)
    
    return render_template('getwell_plans.html', company=company, plans=plans, section_scores=section_scores, overall_score=overall_score, overall_color=overall_color)

@app.route('/calculate_scores/<int:company_id>')
def calculate_scores(company_id):
    """Calculate AI scores for all sections of a company"""
    company = Company.query.get_or_404(company_id)
    
    try:
        results = calculate_all_section_scores(company_id)
        
        if results:
            flash(f'Successfully calculated scores for {len(results)} sections', 'success')
        else:
            flash('No scores could be calculated. Check if you have an OpenAI API key set.', 'warning')
            
    except Exception as e:
        flash(f'Error calculating scores: {str(e)}', 'error')
    
    return redirect(url_for('company_detail', company_id=company_id))

@app.route('/test_upload')
def test_upload():
    """Simple test upload page"""
    return send_file('test_upload.html')

@app.route('/simple_test')
def simple_test():
    """Very simple test upload page"""
    return send_file('simple_test.html')

@app.route('/download_template')
def download_template():
    """Download CSV template"""
    import csv
    from io import StringIO
    
    # Create CSV template
    output = StringIO()
    writer = csv.writer(output)
    
    # Write header
    writer.writerow(['Section', 'Question', 'Answer'])
    
    # Write template rows based on the new questionnaire structure
    template_data = [
        # Section 1: Company Profile & Strategic Alignment
        ['Section 1: Company Profile & Strategic Alignment', 'Company Name', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Primary NAICS Codes (Only GovCon)', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Revenue', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Number of Employees', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Company Type: Basic, Financial Transaction Services, Healthcare, Technology & Government', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'What is your company\'s overall mission and how does AI fit into it?', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Do you have a formal AI strategy or roadmap? If yes, please provide details or documents.', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Which of the following best describes your AI posture?', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Is there a designated AI lead, chief AI officer, or equivalent executive role? If yes, provide name/title.', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Who is responsible to AI strategy within your organization?', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'What % of your internal Executive/Management Team meetings are discussing AI initiatives?', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'What business outcomes are you aiming to achieve with AI over the next 12–24 months?', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Which of the following best describes your AI investment approach? Opportunistic, Strategic, Innovation-led, or Not yet defined', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'In which areas does your leadership see the greatest risk or resistance to AI adoption?', ''],
        ['Section 1: Company Profile & Strategic Alignment', 'Get-Well Plan ‚ Section 1: Company Profile & Strategic Alignment', ''],
        
        # Section 2: AI Capabilities & Technical Maturity
        ['Section 2: AI Capabilities & Technical Maturity', 'Which of the following AI/ML capabilities does your company currently possess or deliver?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'Describe your internal AI development capability (e.g., number of AI/ML engineers, data scientists, tools used).', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'Do you use open-source, proprietary, or government-provided models? Please specify examples.', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'What development frameworks and toolchains are most commonly used?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'Do you have a formal AI/ML lifecycle management system in place?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'Do you conduct independent AI R&D? If yes, list notable efforts, funding sources, or publications.', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'How frequently do you use AI tools in your day-to-day work?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'What types of AI tools do you personally use?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'For which tasks do you most commonly use AI? Include Use Case Summary, if Applicable', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'How confident are you in using AI tools effectively?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'In which business functions is AI currently being used?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'How do you currently measure the impact or success of your AI solutions?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'Which stages of the AI lifecycle are you strongest in, and which need the most improvement?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'Do you follow any AI maturity model or framework to guide capability development?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'What AI capabilities do you consider essential to build or acquire in the next 12–24 months?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'Do you have a data infrastructure strategy?', ''],
        ['Section 2: AI Capabilities & Technical Maturity', 'Get-Well Plan AI Section 2: AI Capabilities & Technical Maturity', ''],
        
        # Section 3: Government AI Integration & Contract Performance (GovCon)
        ['Section 3: Government AI Integration & Contract Performance', 'On which contracts have you delivered AI-enabled capabilities?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'Are you currently on or pursuing any AI-specific IDIQs/BPAs?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'What security clearances or environments can your AI solutions operate within?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'Have you worked with government stakeholders on AI testing, evaluation, red teaming, or risk management?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'How do you ensure explainability, fairness, and ethical AI in federal applications?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'Are your AI tools or models accredited or certified for government use? If yes, list them.', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'How does your company typically introduce AI capabilities to potential government clients?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'Do you use proof-of-concepts (POCs) or minimum viable products (MVPs) to demonstrate AI capabilities? Please provide examples.', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'Are your customers inquiring about use of AI? If so, in what way?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'What risk of disruption does Generative AI pose?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'Are you partnered or subcontracted under any of the Big Primes for AI work?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'How does your AI capability align with current government priorities (e.g., autonomy, ISR, digital workforce)?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'Do you face procurement or regulatory barriers to AI adoption in government environments? If so, describe.', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'Are you participating in any cross-agency AI initiatives, testbeds, or R&D challenges?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'What is your go-to-market strategy for AI solutions in the public sector?', ''],
        ['Section 3: Government AI Integration & Contract Performance', 'Get-Well Plan AI Section 3: Government AI Integration & Contract Performance', ''],
        
        # Section 3: AI Adoption & Compliance in Healthcare Settings (Healthcare)
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'On which healthcare initiatives or products have you delivered AI-enabled capabilities?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'Are you currently involved in or pursuing AI-specific collaborations with healthcare providers, payers, or research institutions?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'What compliance or regulatory environments can your AI solutions operate within? (e.g., HIPAA, FDA, ONC)', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'Have you worked with clinical or regulatory stakeholders on AI validation, risk assessment, or model governance?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'How do you ensure explainability, fairness, and ethical AI in clinical or patient-facing applications?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'Are your AI tools or models accredited, validated, or cleared for use in healthcare? If yes, please list them.', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'How does your company typically introduce AI capabilities to potential healthcare clients?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'Do you use clinical pilots, retrospective studies, or MVPs to demonstrate AI effectiveness? Please provide examples.', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'Are your healthcare customers inquiring about AI? If so, in what context? (e.g., diagnostics, workflow automation, population health)', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'What risk or opportunity does Generative AI pose in healthcare settings?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'Are you partnered with any major health systems, vendors, or academic institutions for AI initiatives?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'How are you addressing clinical validation and real-world evidence for AI in healthcare settings?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'What feedback have you received from clinical or operational users about your AI tools?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'Are your AI tools integrated with any EHRs, medical devices, or digital health platforms?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'What is your go-to-market strategy for AI solutions in the healthcare industry?', ''],
        ['Section 3: AI Adoption & Compliance in Healthcare Settings', 'Get-Well Plan AI Section 3: AI Adoption & Compliance in Healthcare Settings', ''],
        
        # Section 3: AI Integration & Financial Services Delivery (Finance)
        ['Section 3: AI Integration & Financial Services Delivery', 'On which financial products, platforms, or services have you delivered AI-enabled capabilities?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'Are you currently part of any AI-focused fintech accelerators, banking innovation labs, or regulatory sandboxes?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'What regulatory environments can your AI solutions operate within? (e.g., SEC, FINRA, GDPR, PCI DSS)', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'Have you collaborated with internal risk, compliance, or audit teams on AI testing or governance?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'How do you ensure explainability, fairness, and ethical AI in financial decision-making systems?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'Are any of your AI models certified or validated by regulatory or industry bodies? If yes, list them.', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'How does your company introduce AI capabilities to banking, insurance, or capital markets clients?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'Do you use proof-of-concepts (POCs) or MVPs to demonstrate AI capabilities in financial workflows? Please provide examples.', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'Are your customers asking about AI adoption? In what areas? (e.g., fraud detection, credit scoring, trading, customer insights)', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'What disruptive risks or opportunities do you associate with Generative AI in finance?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'Are you partnered with major financial institutions or consultancies for AI work?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'How is your company approaching model governance for AI in regulated financial workflows?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'Are you using AI for real-time risk management or compliance monitoring? If yes, how?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'What role do LLMs or Generative AI play in areas like customer communication, fraud detection, or compliance automation?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'What is your go-to-market strategy for AI offerings in the financial services sector?', ''],
        ['Section 3: AI Integration & Financial Services Delivery', 'Get-Well Plan AI Section 3: AI Integration & Financial Services Delivery', ''],
        
        # Section 4: Partnerships, Ecosystem & Industry Engagement
        ['Section 4: Partnerships, Ecosystem & Industry Engagement', 'Which AI hardware or cloud partners do you actively collaborate with?', ''],
        ['Section 4: Partnerships, Ecosystem & Industry Engagement', 'Are you a participant in any government or academic consortia on AI?', ''],
        ['Section 4: Partnerships, Ecosystem & Industry Engagement', 'Do you have partnerships with any academic institutions for AI research or talent pipeline?', ''],
        ['Section 4: Partnerships, Ecosystem & Industry Engagement', 'Do you collaborate with OpenAI, Anthropic, Cohere, or other foundation model companies?', ''],
        ['Section 4: Partnerships, Ecosystem & Industry Engagement', 'Get-Well Plan AI Section 4: Partnerships, Ecosystem & Industry Engagement', ''],
        
        # Section 5: AI Talent, Culture & Organizational Readiness
        ['Section 5: AI Talent, Culture & Organizational Readiness', 'How many employees work in AI-related roles? Provide counts by function.', ''],
        ['Section 5: AI Talent, Culture & Organizational Readiness', 'Do you have AI-focused hiring goals or workforce development plans?', ''],
        ['Section 5: AI Talent, Culture & Organizational Readiness', 'Does your company offer AI training or upskilling programs internally?', ''],
        ['Section 5: AI Talent, Culture & Organizational Readiness', 'Do you have ethical guidelines or training in place for responsible AI use?', ''],
        ['Section 5: AI Talent, Culture & Organizational Readiness', 'Is AI incorporated into your company business development or proposal writing capabilities?', ''],
        ['Section 5: AI Talent, Culture & Organizational Readiness', 'How is AI being integrated into internal business functions such as HR, marketing, finance, and operations?', ''],
        ['Section 5: AI Talent, Culture & Organizational Readiness', 'Is AI used in any business development, sales, marketing, or proposal-related processes? If so, how?', ''],
        ['Section 5: AI Talent, Culture & Organizational Readiness', 'Is AI used in account planning or customer relationship strategies? If so, describe how it informs targeting, engagement, or pipeline development.', ''],
        ['Section 5: AI Talent, Culture & Organizational Readiness', 'Get-Well Plan AI Section 5: AI Talent, Culture & Organizational Readiness', ''],
        
        # Section 6: Future Readiness & Differentiators
        ['Section 6: Future Readiness & Differentiators', 'What emerging AI capabilities are you investing in?', ''],
        ['Section 6: Future Readiness & Differentiators', 'What do you see as your company\'s competitive advantage in the AI market you serve?', ''],
        ['Section 6: Future Readiness & Differentiators', 'What challenges are you facing in scaling or deploying AI within your target market or client base?', ''],
        ['Section 6: Future Readiness & Differentiators', 'Where do you see your company\'s role in the AI ecosystem over the next 3–5 years?', ''],
        ['Section 6: Future Readiness & Differentiators', 'Are you planning on reducing your workforce and replace it with AI?', ''],
        ['Section 6: Future Readiness & Differentiators', 'Are there any current or upcoming AI initiatives you\'d like to highlight for strategic investment or collaboration?', ''],
        ['Section 6: Future Readiness & Differentiators', 'Get-Well Plan AI Section 6: Future Readiness & Differentiators', '']
    ]
    
    for row in template_data:
        writer.writerow(row)
    
    output.seek(0)
    
    from flask import Response
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=assessment_template.csv'}
    )

@app.route('/download_report/<int:company_id>')
def download_report(company_id):
    """Download PDF report for a company"""
    company = Company.query.get_or_404(company_id)
    
    # Get all assessment data
    sections = get_company_sections(company_id) + ['Section 6: Future Readiness & Differentiators']
    
    section_data = {}
    for section in sections:
        assessments = Assessment.query.filter_by(company_id=company_id, section=section).all()
        section_score = get_section_score(company_id, section)
        section_data[section] = {
            'assessments': assessments,
            'score': section_score,
            'color': get_score_color(section_score)
        }
    
    overall_score = get_overall_score(company_id)
    plans = GetWellPlan.query.filter_by(company_id=company_id).all()
    
    # Generate PDF report
    from reportlab.lib.pagesizes import letter
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.lib import colors
    
    filename = f"report_{company.name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    doc = SimpleDocTemplate(filepath, pagesize=letter)
    styles = getSampleStyleSheet()
    story = []
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30
    )
    story.append(Paragraph(f"AI Assessment Report: {company.name}", title_style))
    story.append(Spacer(1, 12))
    
    # Overall Score
    overall_style = ParagraphStyle(
        'OverallScore',
        parent=styles['Normal'],
        fontSize=16,
        spaceAfter=20
    )
    if overall_score is not None:
        story.append(Paragraph(f"Overall AI Score: {overall_score:.1f}/10", overall_style))
    else:
        story.append(Paragraph("Overall AI Score: N/A", overall_style))
    story.append(Spacer(1, 12))
    
    # Section Scores Table
    section_data_table = [['Section', 'Score']]
    for section in sections:
        score = section_data[section]['score']
        if score is not None:
            section_data_table.append([section, f"{score:.1f}/10"])
        else:
            section_data_table.append([section, "N/A"])
    
    section_table = Table(section_data_table, colWidths=[4*inch, 1*inch])
    section_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 14),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(section_table)
    story.append(Spacer(1, 20))
    
    # Detailed Assessments
    for section in sections:
        story.append(Paragraph(section, styles['Heading2']))
        story.append(Spacer(1, 12))
        
        for assessment in section_data[section]['assessments']:
            if 'Get-Well Plan' not in assessment.question:
                story.append(Paragraph(f"<b>Q: {assessment.question}</b>", styles['Normal']))
                story.append(Paragraph(f"A: {assessment.answer}", styles['Normal']))
                if assessment.score:
                    story.append(Paragraph(f"Score: {assessment.score}/10", styles['Normal']))
                story.append(Spacer(1, 6))
        
        story.append(Spacer(1, 12))
    
    # Get-Well Plans
    if plans:
        story.append(Paragraph("Get-Well Plans", styles['Heading2']))
        story.append(Spacer(1, 12))
        
        for plan in plans:
            story.append(Paragraph(f"<b>{plan.section}</b>", styles['Normal']))
            
            # Convert markdown to PDF formatting
            plan_text = plan.plan_text
            
            # Split into lines and process each line
            lines = plan_text.split('\n')
            for line in lines:
                line = line.strip()
                if not line:
                    story.append(Spacer(1, 6))
                    continue
                
                # Handle different markdown elements
                if line.startswith('### '):
                    # H3 heading
                    heading_text = line[4:].strip()
                    story.append(Paragraph(f"<b>{heading_text}</b>", styles['Heading3']))
                elif line.startswith('#### '):
                    # H4 heading
                    heading_text = line[5:].strip()
                    story.append(Paragraph(f"<b>{heading_text}</b>", styles['Heading4']))
                elif line.startswith('**') and line.endswith('**'):
                    # Bold text
                    bold_text = line[2:-2].strip()
                    story.append(Paragraph(f"<b>{bold_text}</b>", styles['Normal']))
                elif line.startswith('- **'):
                    # Bullet point with bold
                    bullet_text = line[4:].strip()
                    if bullet_text.endswith('**'):
                        bullet_text = bullet_text[:-2]
                        story.append(Paragraph(f"• <b>{bullet_text}</b>", styles['Normal']))
                    else:
                        story.append(Paragraph(f"• {bullet_text}", styles['Normal']))
                elif line.startswith('- '):
                    # Regular bullet point
                    bullet_text = line[2:].strip()
                    story.append(Paragraph(f"• {bullet_text}", styles['Normal']))
                elif line.startswith('---'):
                    # Horizontal rule - add extra space
                    story.append(Spacer(1, 12))
                else:
                    # Regular paragraph
                    if line:
                        story.append(Paragraph(line, styles['Normal']))
            
            story.append(Spacer(1, 12))
    
    doc.build(story)
    
    return send_file(filepath, as_attachment=True, download_name=filename)

if __name__ == '__main__':
    app.run(debug=True) 