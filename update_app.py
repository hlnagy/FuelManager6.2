import os

file_path = r"c:\Users\Nagy H Lajos\.gemini\antigravity\NEW PROIECT\NEW PROIECT\app.py"

with open(file_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Target string (start of the block)
start_marker = "pdf_path, msg = generate_analysis_report_pdf(html, gid)"

if start_marker not in content:
    print("Error: Start marker not found!")
    exit(1)

# Split content
parts = content.split(start_marker)
pre = parts[0] + start_marker
post = parts[1]

# We want to replace the if/else block that follows.
# It ends at `return msg, 500` (original code) or `return jsonify...` (if partially applied, but it failed so likely original).
# But wait, `return msg, 500` is the error case.
# The success case returns `render_template`.

# Let's look for the next function definition to bound our search/replace, or just use indentation.
# The block is indented by 4 spaces (inside `analysis_pdf`? No, inside `analysis_pdf` which is indented?).
# `view_file` showed `    pdf_path, msg = ...` (4 spaces).
# So formatting is:
#     pdf_path, msg = ...
#     if pdf_path:
#         ...
#         return render_template(...)
#         
#     log_debug(...)
#     return msg, 500

# We want to replace everything from after `pdf_path, msg = ...` until `return msg, 500` (inclusive).

end_marker = "return msg, 500"

if end_marker not in post:
    print("Error: End marker not found in post-content!")
    # Debug: print first 500 chars of post
    print("DEBUG POST START:", post[:500])
    exit(1)

# Find end_marker in post
end_idx = post.find(end_marker) + len(end_marker)

# Construct new block
new_block = """
    if pdf_path:
        return jsonify({'status': 'success', 'filepath': pdf_path, 'filename': os.path.basename(pdf_path)})
        
    return jsonify({'status': 'error', 'message': msg}), 500"""

# Reassemble
new_content = pre + new_block + post[end_idx:]

with open(file_path, 'w', encoding='utf-8') as f:
    f.write(new_content)

print("Successfully updated app.py")
