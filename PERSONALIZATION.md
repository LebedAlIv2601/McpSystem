# User Personalization Guide

## Overview

The system now supports comprehensive user personalization. The AI assistant adapts its responses based on your:
- Language and communication preferences
- Development style and technologies
- Work habits and schedule
- Current projects and pain points
- Preferred AI behavior

## Quick Start

### 1. View Example Profile

Send `/profile_example` to the bot to see a complete profile template.

### 2. Create Your Profile

Copy the example, fill with your data, and send as JSON message:

```json
{
  "name": "Your Name",
  "language": "ru",
  "timezone": "Europe/Moscow",
  "development_preferences": {
    "primary_language": "Kotlin",
    "architecture_style": "Clean Architecture + MVI"
  }
}
```

### 3. Verify Profile

Send `/profile` to view your current profile.

## Telegram Commands

| Command | Description |
|---------|-------------|
| `/profile` | View your current profile |
| `/edit_profile` | Get profile editing instructions |
| `/profile_example` | Get complete profile template |
| `/delete_profile` | Delete your profile data |

## Profile Structure

### Required Fields
- `name` - Your name
- `language` - Preferred language (ISO code: `en`, `ru`, etc.)
- `timezone` - Your timezone (e.g., `Europe/Moscow`)

### Optional Sections

#### Personal Info
```json
"personal_info": {
  "role": "Senior Android Developer",
  "experience_years": 8,
  "company": "Your Company"
}
```

#### Communication Preferences
```json
"communication_preferences": {
  "response_style": "concise",  // concise | detailed | balanced
  "tone": "professional",        // professional | casual | formal
  "use_emojis": false,
  "preferred_greeting": "Привет"
}
```

#### Development Preferences
```json
"development_preferences": {
  "primary_language": "Kotlin",
  "secondary_languages": ["Python", "Java"],
  "architecture_style": "Clean Architecture + MVI",
  "code_style": "idiomatic_kotlin",
  "testing_approach": "unit_tests_required",
  "preferred_libraries": ["Jetpack Compose", "Coroutines", "Room"]
}
```

#### Work Habits
```json
"work_habits": {
  "working_hours": "10:00-19:00 MSK",
  "break_time": "14:00-15:00",
  "focus_periods": ["10:00-12:00", "16:00-18:00"],
  "preferred_review_time": "morning"
}
```

#### Project Context
```json
"project_context": {
  "current_projects": ["EasyPomodoro"],
  "main_responsibilities": [
    "Android app development",
    "Architecture decisions"
  ],
  "pain_points": [
    "Legacy code refactoring",
    "Performance optimization"
  ]
}
```

#### AI Assistant Preferences
```json
"ai_assistant_preferences": {
  "explain_code": "step_by_step",     // brief | step_by_step | detailed
  "code_comments": "minimal",         // minimal | standard | verbose
  "suggest_alternatives": true,
  "ask_before_refactoring": true,
  "auto_format_code": true,
  "include_tests": "on_request"       // always | on_request | never
}
```

## How It Works

### Context Injection
Your profile is injected into the AI's system prompt in structured format:
```
===== USER PROFILE =====

Personal Information:
- Name: Александр
- Preferred Language: ru
- Timezone: Europe/Moscow

Development Context (use when discussing code/architecture):
- Primary Language: Kotlin
- Architecture Style: Clean Architecture + MVI
...

AI Assistant Behavior (always apply):
- Code Explanation Style: step_by_step
- Code Comments Level: minimal
...
```

### Smart Usage
The AI model automatically decides which parts of your profile are relevant to each question:
- **Code questions** → Uses development preferences
- **Project questions** → Uses project context
- **General chat** → Uses communication preferences
- **All responses** → Applies AI behavior settings

### Zero Overhead
- No classification step required
- No additional API calls
- Immediate context availability
- Model decides relevance intelligently

## Updating Profile

### Partial Updates
You can update only specific fields:
```json
{
  "language": "en",
  "communication_preferences": {
    "response_style": "detailed"
  }
}
```

Unspecified fields remain unchanged.

### Via API
```bash
curl -X PUT "https://your-server.com/api/profile/YOUR_USER_ID" \
  -H "X-API-Key: YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"data": {"language": "en"}}'
```

## Privacy & Data

- Profiles stored in `server/data/user_profiles.json`
- Each user ID has isolated profile
- Full deletion support (GDPR compliant)
- No profile sharing between users
- Local file storage (no external services)

## API Reference

### Get Profile
```
GET /api/profile/{user_id}
Headers: X-API-Key

Response: { "message": "...", "profile": {...} }
```

### Update Profile
```
PUT /api/profile/{user_id}
Headers: X-API-Key
Body: { "data": {...} }

Response: { "message": "...", "profile": {...} }
```

### Delete Profile
```
DELETE /api/profile/{user_id}
Headers: X-API-Key

Response: { "message": "Profile deleted successfully" }
```

## Examples

### Minimal Profile
```json
{
  "name": "Alex",
  "language": "en",
  "timezone": "UTC"
}
```

### Developer Profile
```json
{
  "name": "Александр",
  "language": "ru",
  "timezone": "Europe/Moscow",
  "development_preferences": {
    "primary_language": "Kotlin",
    "architecture_style": "Clean Architecture + MVI",
    "preferred_libraries": ["Jetpack Compose", "Coroutines"]
  },
  "ai_assistant_preferences": {
    "explain_code": "step_by_step",
    "code_comments": "minimal"
  }
}
```

### Full Profile
See `server/data/profile_example.json` for complete example with all fields.

## Troubleshooting

### Invalid JSON Error
- Check syntax (quotes, commas, brackets)
- Use online JSON validator
- Send `/profile_example` for correct format

### Profile Not Applied
- Verify profile saved: `/profile`
- Check logs for errors
- Restart conversation (clear history)

### Update Not Working
- Ensure valid JSON format
- Check field names match example
- Use `/profile` to verify changes

## Support

For issues or questions about personalization:
1. Check this guide
2. View `/profile_example`
3. Verify with `/profile`
4. Check server logs in Railway dashboard
