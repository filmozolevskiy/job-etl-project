# UI Mockups - Job Search Campaign Management

This directory contains HTML mockups of the Job Search Campaign Management application with a modern, gradient-driven aesthetic featuring rounded cards, clear typography, and numerous call-to-action buttons.

## 🎨 New Structure (Refactored)

The codebase has been refactored to follow best practices with separated concerns:

```
ui_mockups/
├── css/
│   ├── main.css          # Main stylesheet (imports all CSS)
│   ├── base.css          # Base styles, reset, typography, CSS variables
│   ├── components.css     # Reusable UI components (buttons, cards, forms, etc.)
│   ├── layout.css        # Layout styles (sidebar, main content, grids)
│   └── pages.css          # Page-specific styles
├── js/
│   ├── common.js         # Common utilities and form validation
│   ├── sidebar.js        # Sidebar navigation functionality
│   ├── loadSidebar.js    # Sidebar component loader
│   ├── login.js          # Login page specific functionality
│   └── jobDetails.js     # Job details page functionality
├── components/
│   └── sidebar.html      # Sidebar component template
└── *.html                # HTML pages (refactored to use external CSS/JS)
```

### Key Improvements

1. **Separation of Concerns**: CSS, JavaScript, and HTML are now in separate files
2. **DRY Principle**: No code repetition - shared styles and scripts are centralized
3. **CSS Variables**: Design tokens (colors, spacing, etc.) are defined in `base.css`
4. **Component-Based**: Reusable components like sidebar are loaded dynamically
5. **Maintainability**: Easy to update styles or functionality across all pages

## 📄 Pages Included

### 1. **login.html** - Login/Signin Page
   - Email and password login form
   - Sign up form (togglable)
   - Social login buttons (Google, Facebook, LinkedIn) - marked as "Coming soon"
   - Modern gradient design with centered card layout

### 2. **dashboard.html** - Dashboard Page
   - Sidebar navigation
   - Overall statistics cards:
     - Active Campaigns
     - Jobs Found
     - Jobs Applied
     - Success Rate
   - Activity chart placeholder (line graph per day)
   - Last Jobs Applied list

### 3. **campaigns.html** - Campaigns List Page
   - Sidebar navigation
   - List of all campaigns with:
     - Name
     - Owner
     - Location
     - Jobs Found
     - Last Search
     - View, Edit, Delete action buttons
   - "Create New Campaign" button

### 4. **add_campaign.html** - Create New Campaign Page
   - Sidebar navigation
   - Comprehensive form with all campaign fields:
     - Campaign name, query, location, country
     - Date window, email, skills
     - Salary range and currency
     - Remote preference checkboxes
     - Seniority checkboxes
     - Company size preference
     - Employment type preference
     - Ranking weights (optional, with total calculator)
   - Form validation indicators

### 5. **edit_campaign.html** - Edit Campaign Page
   - Same as add_campaign.html but with pre-filled values
   - Save and Cancel buttons

### 6. **campaign_details.html** - Campaign Details & Job Management Page
   - Sidebar navigation
   - Campaign statistics at top:
     - Status (with Paused/Processing states)
     - Jobs Processed (applied / total)
     - Last Update
     - "Find Jobs" button with loading animation showing pipeline status:
       - Looking for jobs
       - Processing jobs
       - Ranking jobs
       - Preparing results
   - Filtering by job status and posted date
   - Jobs list with each job showing:
     - Company logo + Company Name (with Glassdoor link if available)
     - Job Posting title (with link to job details)
     - Rank badge (Bad fit, Moderate fit, Good fit, Perfect fit)
     - Posted At date
     - Status dropdown (found/preparing to apply/applied/waiting for reply/rejected)
     - Approve/Reject action buttons
     - Resume status (No/Generated)
     - Cover Letter status (No/Generated)

### 7. **job_details.html** - Job Details Page
   - Sidebar navigation
   - Job header with company logo, title, and key info
   - Resume section:
     - Resume selector dropdown
     - Generate new resume button
     - Resume preview
   - Cover Letter section:
     - Cover letter selector dropdown
     - Generate new cover letter button
     - Cover letter preview
   - Comments section:
     - List of existing comments
     - Form to add new comments
   - Job Status History timeline

### 8. **resumes.html** - Resumes Management Page (Placeholder)
   - Sidebar navigation
   - Placeholder card with "Coming Soon" message
   - Explains that the page will allow users to:
     - Upload and manage resumes
     - Create multiple resume versions
     - Customize resumes for specific roles
     - Track which resume was used for each application

### 9. **cover_letters.html** - Cover Letters Management Page (Placeholder)
   - Sidebar navigation
   - Placeholder card with "Coming Soon" message
   - Explains that the page will allow users to:
     - Create and manage cover letters
     - Generate personalized cover letters
     - Customize cover letters for specific roles
     - Track which cover letter was used for each application

### 10. **account_management.html** - Account Management Page
   - Sidebar navigation
   - Account Information section displaying:
     - Email address
     - Full name
     - Account type/plan
     - Member since date
   - Change Password form with:
     - Current password field
     - New password field
     - Confirm password field
     - Password validation
   - Logout section with confirmation dialog

## 🎨 Design System

All pages use a consistent modern design system defined in CSS variables:

### Colors (CSS Variables)
- **Primary**: `#7c3aed` (Purple)
- **Primary Dark**: `#6d28d9`
- **Primary Gradient**: `#667eea` to `#764ba2`
- **Background**: `#f5f7fa` (Light Gray)
- **Surface**: `#ffffff` (White)
- **Text Primary**: `#1a1d29` (Dark Gray)
- **Text Secondary**: `#495057` (Medium Gray)
- **Text Muted**: `#6c757d` (Light Gray)

### Typography
- **Font Family**: System font stack (-apple-system, Segoe UI, Roboto, Helvetica Neue, Arial, sans-serif)
- **Base Font Size**: 0.9375rem (15px)
- **Headings**: Bold, varying sizes (1.25rem - 2rem)
- **Body**: 0.9375rem (15px) regular weight
- **Labels**: 0.875rem (14px) with uppercase transformation for table headers

### Components

#### Sidebar Navigation
- Fixed position, full height
- White background with subtle shadow
- 260px width
- Menu items with icons and hover states
- Active state with purple background and left border highlight
- User profile section at bottom

#### Cards
- White background
- 12px border radius
- Subtle box shadows
- 2rem padding
- Hover effects with elevated shadows

#### Buttons
- Multiple variants: primary, secondary, outline
- Rounded corners (8px)
- Hover animations (translateY -1px)
- Shadow effects
- Icon + text combinations

#### Tables
- Gradient header background
- Hover row effects
- Responsive design
- Clean borders and spacing

#### Forms
- 2px borders with focus states
- Focus ring using box-shadow
- Checkbox groups with background sections
- Grid layouts for related fields
- Real-time validation

## 🚀 Features

- ✅ Responsive layout with sidebar navigation
- ✅ Consistent header and navigation
- ✅ Card-based content areas
- ✅ Table layouts with hover effects
- ✅ Button styles and states
- ✅ Form inputs and validation
- ✅ Status badges and indicators
- ✅ Statistics displays
- ✅ Loading animations
- ✅ Filtering capabilities
- ✅ Document management (Resumes, Cover Letters)
- ✅ Comments system
- ✅ Status history timeline
- ✅ Modern gradient design elements
- ✅ CSS Variables for easy theming
- ✅ Separated CSS, JS, and HTML
- ✅ Component-based architecture

## 📁 File Structure

### CSS Files
- **base.css**: CSS variables, reset, typography
- **components.css**: Buttons, cards, forms, badges, tables
- **layout.css**: Sidebar, main content, grid layouts
- **pages.css**: Page-specific styles (login, dashboard, job details, etc.)
- **main.css**: Main entry point that imports all CSS files

### JavaScript Files
- **common.js**: Utility functions, form validation, notifications
- **sidebar.js**: Sidebar navigation functionality
- **loadSidebar.js**: Dynamic sidebar component loader
- **login.js**: Login/signup form handling
- **jobDetails.js**: Job details page interactions

### Components
- **sidebar.html**: Reusable sidebar component template

## 🔧 Usage

### For Pages with Sidebar

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page Title</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <link rel="stylesheet" href="css/main.css">
</head>
<body>
    <div class="sidebar-container"></div>
    
    <main class="main-content">
        <!-- Your page content here -->
    </main>
    
    <script src="js/common.js"></script>
    <script src="js/sidebar.js"></script>
    <script src="js/loadSidebar.js"></script>
    <!-- Add page-specific JS if needed -->
</body>
</html>
```

### For Login Page

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login</title>
    <link rel="stylesheet" href="css/main.css">
</head>
<body class="login-page">
    <!-- Login content -->
    
    <script src="js/common.js"></script>
    <script src="js/login.js"></script>
</body>
</html>
```

## 🎯 Best Practices Implemented

1. **Separation of Concerns**: CSS, JavaScript, and HTML are in separate files
2. **DRY (Don't Repeat Yourself)**: Shared code is centralized
3. **CSS Variables**: Design tokens for easy theming
4. **Component Reusability**: Sidebar and other components are reusable
5. **Accessibility**: Focus states, semantic HTML, ARIA attributes
6. **Responsive Design**: Mobile-friendly layouts
7. **Performance**: External CSS/JS files can be cached
8. **Maintainability**: Easy to update styles or functionality

## 📝 Notes

- Social login buttons (Google, Facebook, LinkedIn) are shown but marked as "Coming soon"
- The activity chart on the dashboard is a placeholder
- Resumes and Cover Letters pages are placeholders with "Coming Soon" messages
- All interactive elements have appropriate hover and focus states
- The design follows modern SaaS dashboard patterns with gradient accents
- Company logos are placeholder initials in colored boxes (can be replaced with actual logos)
- Glassdoor links are included where company information is available
- Form validation is implemented with real-time feedback
- Sidebar is loaded dynamically for better maintainability

## 🔄 Migration Notes

If you're updating existing pages:

1. Remove all `<style>` tags and move styles to appropriate CSS files
2. Remove all `<script>` tags and move scripts to appropriate JS files
3. Replace sidebar HTML with `<div class="sidebar-container"></div>`
4. Add the required script tags at the bottom of the body
5. Use CSS classes from the component library instead of inline styles
6. Use CSS variables for colors and spacing

## 📖 How to View

Simply open any of these HTML files in your web browser to see the UI design and layout. All pages use external CSS and JavaScript files, so make sure all files are in the correct directory structure.

For local development, you may need to serve the files through a local web server (e.g., `python -m http.server` or `npx serve`) to avoid CORS issues when loading the sidebar component.
