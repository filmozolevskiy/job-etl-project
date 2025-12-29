# Figma Design Specification - Job Search Campaign Management UI

This document provides detailed specifications for creating the UI designs in Figma.

## Design System

### Colors
- **Primary Blue**: `#007bff` (Buttons, Headers, Links)
- **Primary Blue Hover**: `#0056b3`
- **Success Green**: `#28a745` (Success messages, badges, positive states)
- **Success Green Hover**: `#218838`
- **Danger Red**: `#dc3545` (Delete buttons, errors)
- **Danger Red Hover**: `#c82333`
- **Secondary Gray**: `#6c757d` (Secondary buttons, inactive states)
- **Secondary Gray Hover**: `#545b62`
- **Background Gray**: `#f5f5f5` (Page background)
- **Card White**: `#ffffff` (Cards, tables)
- **Border Gray**: `#dee2e6` (Borders, dividers)
- **Text Primary**: `#333333` (Main text)
- **Text Secondary**: `#6c757d` (Secondary text, labels)
- **Table Header BG**: `#f8f9fa`
- **Flash Success BG**: `#d4edda`
- **Flash Success Border**: `#c3e6cb`
- **Flash Success Text**: `#155724`
- **Flash Error BG**: `#f8d7da`
- **Flash Error Border**: `#f5c6cb`
- **Flash Error Text**: `#721c24`

### Typography
- **Font Family**: System font stack
  - `-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif`
- **H1 (Header)**: 1.5rem (24px), Bold, White
- **Card Header**: 1.25rem (20px), Bold, #333
- **Body Text**: 1rem (16px), Regular, #333
- **Small Text**: 0.875rem (14px), Regular, #6c757d
- **Table Header**: 1rem (16px), Semi-bold (600), #333
- **Button Text**: 0.9rem (14.4px), Regular

### Spacing
- **Container Max Width**: 1200px
- **Container Padding**: 20px
- **Card Padding**: 1.5rem (24px)
- **Section Margin**: 2rem (32px)
- **Form Group Margin**: 1rem (16px)
- **Button Padding**: 0.5rem 1rem (8px 16px)
- **Table Cell Padding**: 0.75rem (12px)
- **Border Radius**: 4px (all rounded elements)

### Shadows
- **Card Shadow**: `0 2px 4px rgba(0,0,0,0.1)`
- **Header Shadow**: `0 2px 4px rgba(0,0,0,0.1)`

---

## Page 1: Dashboard (All Campaigns)

### Layout Structure
- **Width**: 1200px max-width, centered
- **Background**: #f5f5f5

### Header Component
- **Height**: Auto (padding: 1rem 0)
- **Background**: #007bff
- **Text Color**: White
- **Elements**:
  - Title: "Job Search Campaign Management" (H1, left-aligned)
  - Navigation: Horizontal links (All Campaigns, Create Campaign, Jobs)
  - User Section: Right-aligned (Username, Logout link)

### Main Card
- **Background**: White
- **Padding**: 1.5rem
- **Border Radius**: 4px
- **Shadow**: 0 2px 4px rgba(0,0,0,0.1)

#### Card Header
- **Height**: Auto
- **Border Bottom**: 2px solid #007bff
- **Padding Bottom**: 0.5rem
- **Layout**: Flex, space-between
  - Left: "All Campaigns" text
  - Right: "Run All DAGs" button (Green)

#### Table
- **Width**: 100%
- **Background**: White
- **Border Collapse**: Separate
- **Border Radius**: 4px

**Table Header Row**:
- Background: #f8f9fa
- Font Weight: 600
- Padding: 0.75rem
- Columns: ID, Name, Owner, Status, Query, Location, Country, Email, Runs, Last Run, Actions

**Table Data Rows**:
- Padding: 0.75rem
- Border Bottom: 1px solid #dee2e6
- Hover: Background #f8f9fa

**Status Badge**:
- Padding: 0.25rem 0.5rem
- Border Radius: 4px
- Font Size: 0.75rem
- Font Weight: 600
- Success: #28a745 bg, white text
- Secondary: #6c757d bg, white text

**Action Buttons** (in table):
- Size: Small (0.25rem 0.5rem padding, 0.8rem font)
- Spacing: 0.5rem between buttons
- Colors: Primary blue, Secondary gray

---

## Page 2: Jobs Page

### Layout Structure
Same as Dashboard

### Jobs Card Header
- **Layout**: Flex, space-between
- **Left**: "Jobs - [Campaign Name]" (Card Header style)
- **Right**: "Back to Campaign" button (Secondary gray)

### Jobs Table
**Columns**: Company Name, Status, Updated At, Job Posting, Perfect Fit, Notes

**Status Dropdown**:
- Padding: 0.25rem 0.5rem
- Border: 1px solid #ced4da
- Border Radius: 4px
- Font Size: 0.875rem

**Perfect Fit Score**:
- Font Weight: 600
- Color: #28a745
- Format: "[Score] Perfect fit"

**Job Posting Link**:
- Color: #007bff
- Icon: 🔗 emoji or link icon
- Hover: Underline

**Notes**:
- Icon: 📝 (if note exists) or ➕ (if no note)
- Preview: Max-width 200px, ellipsis overflow
- Color: #6c757d for preview text
- Icon Color: #007bff, hover #0056b3

---

## Page 3: Create Campaign Form

### Layout Structure
Same as Dashboard

### Form Card
- Same card styling as Dashboard

### Form Fields Layout

**Standard Input Fields**:
- Width: 100%
- Padding: 0.5rem
- Border: 1px solid #ced4da
- Border Radius: 4px
- Font Size: 1rem

**Labels**:
- Display: Block
- Margin Bottom: 0.5rem
- Font Weight: 500

**Salary Range Section** (3-column grid):
- Grid: 1fr 1fr 1fr
- Gap: 1rem
- Fields: Min Salary, Max Salary, Currency

**Checkbox Groups**:
- Layout: Horizontal inline
- Spacing: 1rem between checkboxes
- Label: Normal font weight (not bold)

**Ranking Weights Section**:
- Title: H3 (2rem margin-top, 1rem margin-bottom)
- Description: Gray text (#6c757d), 1rem margin-bottom
- Grid: 2 columns, 1rem gap
- 9 input fields total
- Total Display: Background #f8f9fa, padding 0.75rem, border-radius 4px

**Form Actions**:
- Margin Top: 1.5rem
- Buttons: Primary (Create) and Secondary (Cancel)
- Spacing: 0.5rem between buttons

---

## Page 4: View Campaign

### Layout Structure
Same as Dashboard

### Campaign Header
- **Layout**: Flex, space-between
- **Left**: "Campaign: [Name]"
- **Right**: Status badge

### Action Buttons Row
- **Layout**: Horizontal
- **Spacing**: 0.5rem between buttons
- **Buttons**: Edit (Primary), View Jobs (Primary), Run DAG (Success), Deactivate (Secondary), Delete (Danger)

### Search Criteria Table
- Same table styling as Dashboard
- **Columns**: Label (200px width) | Value
- **Rows**: Query, Location, Country, Date Window, Skills, Salary Range, Currency, Remote Preference, Seniority, Company Size, Employment Type, Email

### Statistics Grid
- **Layout**: CSS Grid
- **Grid Template**: `repeat(auto-fit, minmax(200px, 1fr))`
- **Gap**: 1rem
- **Items**: 
  - Background: #f8f9fa
  - Padding: 1rem
  - Border Radius: 4px
  - Text Align: Center
  - Stat Value: 2rem font, 600 weight, #007bff color
  - Stat Label: 0.9rem font, #6c757d color, 0.5rem margin-top

### Timestamps Table
- Same styling as Search Criteria Table
- **Rows**: Created At, Updated At, Last Run At

---

## Component Specifications

### Buttons

**Primary Button**:
- Background: #007bff
- Text: White
- Padding: 0.5rem 1rem
- Border Radius: 4px
- Font Size: 0.9rem
- Hover: #0056b3

**Secondary Button**:
- Background: #6c757d
- Text: White
- Same sizing as Primary
- Hover: #545b62

**Success Button**:
- Background: #28a745
- Text: White
- Same sizing as Primary
- Hover: #218838

**Danger Button**:
- Background: #dc3545
- Text: White
- Same sizing as Primary
- Hover: #c82333

**Small Button** (for table actions):
- Padding: 0.25rem 0.5rem
- Font Size: 0.8rem
- Same colors as regular buttons

### Badges

**Success Badge**:
- Background: #28a745
- Text: White
- Padding: 0.25rem 0.5rem
- Border Radius: 4px
- Font Size: 0.75rem
- Font Weight: 600

**Secondary Badge**:
- Background: #6c757d
- Text: White
- Same sizing as Success Badge

### Cards

- Background: White
- Padding: 1.5rem
- Border Radius: 4px
- Box Shadow: 0 2px 4px rgba(0,0,0,0.1)
- Margin Bottom: 1rem

### Form Inputs

**Text/Email/Number Inputs**:
- Width: 100%
- Padding: 0.5rem
- Border: 1px solid #ced4da
- Border Radius: 4px
- Font Size: 1rem
- Background: White

**Select Dropdowns**:
- Same styling as text inputs

**Checkboxes**:
- Width: Auto
- Margin Right: 0.5rem

**Textarea**:
- Same styling as text inputs
- Min Height: 5 rows

### Tables

- Width: 100%
- Border Collapse: Separate
- Background: White
- Border Radius: 4px
- Overflow: Hidden

**Header Row**:
- Background: #f8f9fa
- Font Weight: 600
- Padding: 0.75rem

**Data Rows**:
- Padding: 0.75rem
- Border Bottom: 1px solid #dee2e6
- Hover: Background #f8f9fa

---

## Recommended Figma Setup

1. **Create Frames** for each page:
   - Dashboard: 1440px width (to show max-width container)
   - Jobs Page: 1440px width
   - Create Campaign: 1440px width
   - View Campaign: 1440px width

2. **Create Components** for reusable elements:
   - Button (Primary, Secondary, Success, Danger variants)
   - Badge (Success, Secondary variants)
   - Card
   - Table Row
   - Form Input
   - Navigation Header

3. **Use Auto Layout** for:
   - Header navigation
   - Button groups
   - Form fields
   - Statistics grid
   - Table rows

4. **Create Color Styles**:
   - All colors listed above

5. **Create Text Styles**:
   - H1 Header
   - Card Header
   - Body Text
   - Small Text
   - Table Header
   - Button Text

---

## Sample Data for Mockups

### Dashboard Table
- Campaign 1: "Data Engineer - Remote", Active, 15 runs, Last: 2024-01-15 10:30 ✓ Success
- Campaign 2: "BI Developer - Hybrid", Active, 8 runs, Last: 2024-01-14 14:20 ✓ Success
- Campaign 3: "Python Developer", Inactive, 3 runs, Last: 2024-01-10 09:15 ✗ Error

### Jobs Table
- TechCorp Inc., Applied, 92 Perfect Fit, Note: "Great company culture"
- DataViz Solutions, Waiting, 85 Perfect Fit, No note
- Analytics Pro, Interview, 78 Perfect Fit, Note: "Interview scheduled"

### View Campaign Stats
- Total Runs: 15
- Last Run Jobs: 42
- Last Run Status: ✓
- Avg Ranking Score: 85.3
- Total Ranked Jobs: 156
- Success Rate: 92.5%
- Jobs (Last 30 Days): 38

---

This specification provides all the details needed to recreate your UI designs accurately in Figma!

