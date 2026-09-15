import re

def auto_wrap_mermaid_text(markdown):
    """
    Автоматично форматує та виправляє синтаксичні помилки в блоках Mermaid
    """
    def wrap_label(text, max_chars=24):
        # Якщо текст вже містить теги переносу або перенесення рядків, не чіпаємо
        if '<br' in text or '\n' in text:
            return text
        
        words = text.split()
        if not words:
            return text
        
        lines = []
        curr_line = []
        curr_len = 0
        
        for w in words:
            if curr_len + len(w) + (1 if curr_line else 0) > max_chars and curr_line:
                lines.append(" ".join(curr_line))
                curr_line = [w]
                curr_len = len(w)
            else:
                curr_line.append(w)
                curr_len += len(w) + (1 if len(curr_line) > 1 else 0)
        
        if curr_line:
            lines.append(" ".join(curr_line))
            
        return "<br/>".join(lines)

    def sanitize_label_html(text):
        # Замінюємо знак '<', якщо це не валідний HTML тег (наприклад, '<br/>', '<b>')
        text = re.sub(r'<(?!\/?(?:br|b|i|span|sub|sup)\b[\s\/>])', '&lt;', text)
        # Замінюємо знак '>' якщо це порівняння, наприклад '> 5 с'
        text = re.sub(r'(?<=\s)>(?=\s|\d)', '&gt;', text)
        return text

    def process_mermaid_block(match):
        code = match.group(1)

        # 1. Обробка stateDiagram: виправляємо дужку '}', приліплену до переходу
        if 'stateDiagram' in code:
            code = re.sub(r'(:\s*[^}\n\r]+)\}\s*$', r'\1\n    }', code, flags=re.MULTILINE)
            return f"```mermaid\n{code}\n```"

        # 2. Обробка flowchart / graph
        if 'flowchart' in code or 'graph ' in code:
            # Автоматично виправляємо неіснуючі стрілки з трьома дефісами (<---> або ---->)
            code = re.sub(r'<-{3,}->', '<-->', code)
            code = re.sub(r'(?<!<)-{3,}>', '-->', code)

            # Автоматично лікуємо раніше пошкоджені подвійні лапки всередині вузлів: (" ... ") -> (« ... »)
            code = re.sub(r'\(\"([^\n\r\"]*?)\"\)', r"(«\1»)", code)

            # Обробка ВЖЕ залапкованих вузлів: ID["текст"], ID("текст"), [("текст")], |"текст"| тощо.
            # Тут шукаємо повний текст вузла і НЕ розбиваємо його по внутрішніх дужках ()
            def fix_quoted_nodes(m):
                prefix = m.group(1)
                open_b = m.group(2)
                content = m.group(3)
                close_b = m.group(4)

                content = sanitize_label_html(content)
                wrapped = wrap_label(content.strip(), max_chars=24)
                return f"{prefix}{open_b}{wrapped}{close_b}"

            quoted_pattern = re.compile(
                r'((?:subgraph\s+[\w\-]+|[\w\-]+)?\s*)'
                r'(\[\(\"|\(\[\"|\[\[\"|\(\(\"|\{\{\"?|\[\"|\(\"|\{\"|\>\"|\|\")'
                r'([^"\n\r]+?)'
                r'(\"\)\]|\"\]\)|\"\]\]|\"\)\)|\"\}\}?|\"\]|\"\)|\"\}|\"\|)'
            )
            code = quoted_pattern.sub(fix_quoted_nodes, code)

            # Обробка НЕзалапкованих вузлів: ID[текст], ID(текст) тощо.
            # Обов'язково вимагається ID перед дужкою, щоб не чіпати круглі дужки всередині тексту
            def fix_unquoted_nodes(m):
                prefix = m.group(1)
                open_b = m.group(2)
                content = m.group(3)
                close_b = m.group(4)

                content = sanitize_label_html(content)
                wrapped = wrap_label(content.strip(), max_chars=24)

                # Якщо додався <br/>, обов'язково огортаємо в подвійні лапки
                if '<br/>' in wrapped:
                    quote_map = {
                        '[': ('["', '"]'),
                        '(': ('("', '")'),
                        '{': ('{"', '"}'),
                        '>': ('>"', '"]'),
                        '([': ('(["', '"])'),
                        '[(': ('[("', '")]'),
                        '[[': ('[["', '"]]'),
                        '((': ('(("', '"))'),
                        '{{': ('{{"', '"}}'),
                    }
                    new_open, new_close = quote_map.get(open_b, (open_b + '"', '"' + close_b))
                    return f"{prefix}{new_open}{wrapped}{new_close}"

                return f"{prefix}{open_b}{wrapped}{close_b}"

            unquoted_pattern = re.compile(
                r'((?:subgraph\s+[\w\-]+|[\w\-]+)\s*)'
                r'(\[\(|\(\[|\[\[|\(\(|\{\{|\[|\(|\{|\>)'
                r'([^\[\]\(\)\{\}\>\"\|\n\r]+?)'
                r'(\)\]|\]\)|\b\]\]|\)\)|\}\}|\b\]|\)|\}|\>\])'
            )
            code = unquoted_pattern.sub(fix_unquoted_nodes, code)

        return f"```mermaid\n{code}\n```"

    return re.sub(r'```mermaid\s*\n([\s\S]*?)\n```', process_mermaid_block, markdown)


def on_page_markdown(markdown, page, config, files):
    # 0. Автоматичний перенос та виправлення Mermaid
    markdown = auto_wrap_mermaid_text(markdown)

    # 1. Автоматично перетворюємо блоки ```math ... ``` на $$ ... $$
    markdown = re.sub(r'```math\s*\n([\s\S]*?)\n```', r'\n$$\n\1\n$$\n', markdown)

    # 2. Додаємо порожній рядок перед списками (- або * або 1.), якщо його немає
    # Безпечно обробляємо ТІЛЬКИ текст поза блоками коду ```
    parts = re.split(r'(```[\s\S]*?```)', markdown)
    for i in range(0, len(parts), 2):  # парні індекси — звичайний Markdown текст
        parts[i] = re.sub(r'([^\n])\n([ \t]*[-*+]|\d+\.)\s+', r'\1\n\n\2 ', parts[i])
    markdown = ''.join(parts)

    # 3. Замінюємо знак '<' у математичних блоках $$ на '\lt', щоб не ламався HTML
    def fix_math_tags(match):
        math_content = match.group(0)
        return re.sub(r'<(\s*[0-9a-zA-Z_])', r'\\lt \1', math_content)

    markdown = re.sub(r'\$\$[\s\S]*?\$\$', fix_math_tags, markdown)

    return markdown
