"""Compiled-PDF body-page requirement. Boundary classification remains reviewed evidence."""
import hashlib
import json
import os


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_pages(main, texts, policy, final=False):
    minimum = policy.get('minimum_body_pages')
    if minimum is None:
        return None
    if type(minimum) is not int or minimum < 1:
        raise ValueError('minimum_body_pages must be a positive integer')
    maximum = policy.get('maximum_body_pages')
    if maximum is not None and (type(maximum) is not int or maximum < minimum):
        raise ValueError('maximum_body_pages must be an integer >= minimum_body_pages')
    main = main.resolve()
    pdf = main.with_suffix('.pdf')
    audit = main.parent.parent / 'checks/body_pages.json'
    issues = []
    result = dict(minimum_body_pages=minimum, maximum_body_pages=maximum, pdf=str(pdf), pdf_total_pages=None,
                  verified_body_pages=None, audit=str(audit), issues=issues,
                  scope='PDF physical page count; body classification relies on reviewed page evidence. No automatic semantic boundary inference or layout-quality certification.')
    def issue(code, detail):
        issues.append(dict(level='error' if final else 'warning', code=code, file=str(main), detail=detail))
    if not pdf.is_file():
        issue('body_pages_pdf_missing', '正文页数需编译后的PDF；当前未找到PDF。')
        return result
    try:
        from pypdf import PdfReader
        total = len(PdfReader(pdf).pages)
    except Exception as exc:
        issue('body_pages_pdf_unreadable', f'无法核对PDF物理页数：{type(exc).__name__}: {exc}')
        return result
    result['pdf_total_pages'] = total
    result['pdf_sha256'] = sha(pdf)
    if total < minimum:
        issue('body_pages_below_minimum', f'整份PDF仅{total}页，正文不可能达到{minimum}页；需补充有证据的研究内容。')
        return result
    if not audit.is_file():
        issue('body_page_audit_missing', 'PDF总页数不能代替正文页数；缺少逐页核对后的body_pages.json。')
        return result
    try:
        data = json.loads(audit.read_text(encoding='utf-8-sig'))
        expected = {os.path.relpath(p.resolve(),main.parent).replace('\\','/'): sha(p) for p in texts}
        if not isinstance(data, dict) or data.get('schema_version') != 1 or data.get('reviewed') is not True:
            raise ValueError('audit must be schema 1 and reviewed=true')
        if data.get('pdf_sha256') != sha(pdf) or data.get('tex_sha256') != expected:
            raise ValueError('PDF/source hashes differ from reviewed audit')
        pages = data.get('body_pages')
        if not isinstance(pages, list) or not pages or any(type(p) is not int or not 1 <= p <= total for p in pages) or len(set(pages)) != len(pages):
            raise ValueError('body_pages must be unique 1-based physical page numbers within PDF')
        if not isinstance(data.get('boundary_evidence'), str) or not data['boundary_evidence'].strip():
            raise ValueError('boundary_evidence must explain body boundaries and mixed pages')
        count = len(pages)
        result['verified_body_pages'] = count
        if count < minimum:
            issue('body_pages_below_minimum', f'经核对正文{count}页，低于{minimum}页。')
        if maximum is not None and count > maximum:
            issue('body_pages_above_maximum', f'经核对正文{count}页，超过{maximum}页。')
    except (ValueError, TypeError, OSError) as exc:
        issue('body_page_audit_invalid', str(exc))
    return result
