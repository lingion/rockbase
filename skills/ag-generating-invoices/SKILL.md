---
name: generating-invoices
description: Generates professional A4 invoices for the Social Agency in Markdown and HTML. Use when the user needs to create, issue, or draft an invoice. The skill handles currency selection (USD default), sequential numbering, and persistent archival in the Finance directory.
---

# Generating Invoices

This skill facilitates the professional generation and archival of invoices for the Social Agency. It ensures consistency in layout (A4), currency handling, and sequential numbering.

## Initial Setup & Context
Before proceeding, scan the `Agency/Finance/Invoices/Records/` directory to identify the last issued invoice number and suggest the next sequence (e.g., if the latest is `STNBPLG-0003`, suggest `STNBPLG-0004`).

## Mandatory User Interaction (The "Invoice Intake" Prompt)
Upon activation, the agent MUST immediately ask the user for the following details in a single, structured message:

1.  **Currency**: Confirmation of currency (Default: **USD $**).
2.  **Invoice Number**: Suggest the next sequential number (e.g., `STNBPLG-0004`) based on the latest record in `Agency/Finance/Invoices/Records/`.
3.  **Bill To**: Client Company Name and Address.
4.  **Issue & Due Date**: Dates for the invoice (Defaults to today if not specified).
5.  **Line Items**: List of services and amounts (**Note: User-provided amounts are PRE-TAX Subtotal by default**).
6.  **Footer Notices**: Any specific VAT or bank transfer notes.

## Production Workflow

### Step 1: Data Collection & MD Draft
Collect info from the user and generate a Markdown source file in `Agency/Finance/Invoices/Records/[INVOICE_NO].md`.

**Markdown Schema:**
```markdown
[invoice_no]: STNBPLG-00XXX
[issue_date]: Month Day, Year
[due_date]: Month Day, Year
[total_amount]: $X,XXX.XX
[subtotal]: $X,XXX.XX
[tax_amount]: $X,XXX.XX

[company_name]: Beijing Pan Shi Zhi Shang Technology Co.,Ltd.
[company_address_1]: Room 113-40, 1st Floor, Building 17, Nanli
[company_address_2]: Wulidian, Lugouqiao, Fengtai District, Beijing
[company_country]: China

[client_name]: [Input from User]
[client_address]: [Input from User]

[payment_method]: Bank Transfer

## 🛒 Items
- Item Description | $Amount
```

### Step 2: HTML Generation
Execute the bundled Python script to transform the MD draft into a professional A4 HTML document.

**Command:**
```bash
python .agent/skills/ag-generating-invoices/scripts/generate.py "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/Agency/Finance/Invoices/Records/[INVOICE_NO].md"
```

### Step 3: Layout & Storage
- **Page Size**: Fixed at **A4** (210mm x 297mm) via `assets/style.css`.
- **Currency**: Ensure the currency symbol is prefixing all monetary values.
- **Paths**: Save all records to `${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency/Agency/Finance/Invoices/Records/`.

## Output Delivery
Once files are created, provide the user with:
- The finalized Invoice Number.
- Direct links to the `.md` source and `.html` preview.
- A request to verify the A4 layout and totals.
