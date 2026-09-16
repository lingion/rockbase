import os
import re
import json
import sys

WORKSPACE_ROOT = "${ROCKBASE_HOME}/Library/Mobile Documents/iCloud~md~obsidian/Documents/My Vault/400 🔴 Project/🔴 420 Social Agency"
DEFAULT_RECORDS_PATH = os.path.join(WORKSPACE_ROOT, "Agency/Finance/Invoices/Records")

def parse_markdown(md_path):
    """Robustly parses markdown line by line to avoid cross-line leakage."""
    if not os.path.exists(md_path):
        return None
    
    data = {}
    items = []
    
    with open(md_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            
            # Match [key]: value
            attr_match = re.match(r'^\[(\w+)\]:\s*(.*)', line)
            if attr_match:
                key, value = attr_match.groups()
                data[key.strip()] = value.strip()
                continue
                
            # Match line items: - Description | Amount
            if line.startswith('-'):
                item_parts = line[1:].split('|')
                if len(item_parts) >= 2:
                    items.append({
                        "description": item_parts[0].strip(),
                        "amount": item_parts[-1].strip()
                    })
    
    data['items'] = items
    return data

def generate_invoice(input_path=None):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(os.path.dirname(script_dir), 'assets')
    template_path = os.path.join(assets_dir, 'template.html')
    
    records_path = DEFAULT_RECORDS_PATH
    os.makedirs(records_path, exist_ok=True)

    try:
        if not os.path.exists(template_path):
            print(f"Error: Template not found")
            return

        with open(template_path, 'r', encoding='utf-8') as f:
            template = f.read()
        
        data = parse_markdown(input_path)
        if not data:
            print("Error: Could not parse data.")
            return

        # Backward compatibility for older invoices that only store a single
        # client_address field.
        if data.get("client_address") and not data.get("client_address_1"):
            data["client_address_1"] = data["client_address"]

        # Process line items
        items_html = ""
        for item in data.get('items', []):
            items_html += f'<tr><td class="text-left"><span class="item-desc">{item.get("description", "")}</span></td><td class="text-right">{item.get("amount", "")}</td></tr>'
        
        output = template
        output = output.replace('{{line_items}}', items_html)
        
        # Handle optional tax row (Hide if $0.00)
        if data.get('tax_amount') in ['$0.00', '0', '0.00', '']:
            tax_row_pattern = r'<div class="total-row">\s*<span>Tax \(1%\)</span>\s*<span>{{tax_amount}}</span>\s*</div>'
            output = re.sub(tax_row_pattern, '', output)

        # Precise replacement for {{key}}
        # We define a fixed list of keys we expect in the template
        standard_keys = [
            "invoice_no", "issue_date", "due_date", "company_name", 
            "company_address_1", "company_address_2", "company_country",
            "client_name", "client_address", "client_address_1",
            "client_address_2", "client_country", "total_amount", "subtotal", 
            "tax_amount", "payment_method", "footer_notice_1", "footer_notice_2"
        ]
        
        for key in standard_keys:
            val = data.get(key, "")
            output = output.replace(f'{{{{{key}}}}}', val)

        # Cleanup any missed {{placeholder}}
        output = re.sub(r'\{\{.*?\}\}', '', output)
        output = re.sub(r'\s*<p>\s*</p>\s*', '\n', output)

        # Final naming and save
        inv_no = data.get('invoice_no', 'STNBPLG-XXXX')
        record_html = os.path.join(records_path, f"{inv_no}.html")

        with open(record_html, 'w', encoding='utf-8') as f:
            f.write(output)
            
        print(f"--- Success ---")
        print(f"Invoice: {inv_no}")
        print(f"File:    {record_html}")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python generate.py <path>")
    else:
        generate_invoice(sys.argv[1])
