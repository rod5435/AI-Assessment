# 🔒 Security Guidelines

## API Key Security

### ✅ **Current Security Status**
- **OpenAI API Key**: Properly stored in `.env` file (excluded from git)
- **No hardcoded keys**: All API keys are loaded from environment variables
- **Git exclusion**: `.env` file is properly ignored by git
- **Virtual environment**: `venv/` directory is excluded from version control

### 🛡️ **Security Best Practices**

#### 1. **Environment Variables**
```bash
# ✅ CORRECT - Store in .env file (not committed to git)
OPENAI_API_KEY=your-actual-api-key-here

# ❌ WRONG - Never hardcode in source code
openai.api_key = "sk-..."
```

#### 2. **Git Security**
- ✅ `.env` file is in `.gitignore`
- ✅ `venv/` directory is excluded
- ✅ Database files (`*.db`, `*.sqlite`) are excluded
- ✅ Upload directories are excluded

#### 3. **API Key Management**
- **Never commit API keys** to version control
- **Use environment variables** for all sensitive data
- **Rotate keys regularly** if compromised
- **Use different keys** for development/production

### 🔍 **Security Checklist**

Before committing code:
- [ ] No API keys in source code
- [ ] No hardcoded secrets
- [ ] `.env` file is in `.gitignore`
- [ ] Virtual environment is excluded
- [ ] Database files are excluded
- [ ] Run `git status` to verify no sensitive files

### 🚨 **If API Key is Compromised**

1. **Immediately revoke** the compromised key in OpenAI dashboard
2. **Generate new API key**
3. **Update `.env` file** with new key
4. **Check git history** for any accidental commits
5. **Force push** to remove sensitive data from history if needed

### 📋 **Environment Setup**

Create `.env` file in project root:
```bash
# Flask Configuration
SECRET_KEY=your-secret-key-change-in-production
FLASK_ENV=development

# OpenAI Configuration
OPENAI_API_KEY=your-openai-api-key-here

# Database Configuration
DATABASE_URL=sqlite:///govcon_ai_assessments.db
```

### 🔐 **Production Security**

For production deployment:
- Use strong, unique `SECRET_KEY`
- Set `FLASK_ENV=production`
- Use environment variables for all configuration
- Consider using a secrets management service
- Enable HTTPS/TLS
- Regular security updates

---

**Remember**: Security is everyone's responsibility. When in doubt, ask before committing sensitive information.
