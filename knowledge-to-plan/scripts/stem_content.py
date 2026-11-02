"""Validate optional formula/diagram structure; mathematical truth needs source review."""
import math
import re
import xml.etree.ElementTree as ET

MATH_NS = 'http://www.w3.org/1998/Math/MathML'
SVG_NS = 'http://www.w3.org/2000/svg'
MATH_TAGS = set('math mrow mi mn mo mtext mfrac msqrt mroot msup msub msubsup munder mover munderover mtable mtr mtd mspace mstyle'.split())
MATH_ATTRS = set('display mathvariant displaystyle scriptlevel stretchy fence separator accent accentunder linethickness columnalign rowalign columnspacing rowspacing notation width height depth lspace rspace mathsize mathcolor mathbackground aria-label'.split())
SVG_TAGS = set('svg g defs marker path rect circle ellipse line polyline polygon text tspan title desc linearGradient radialGradient stop'.split())
SVG_ATTRS = set('id viewBox width height x y x1 y1 x2 y2 cx cy r rx ry d points fill fill-opacity fill-rule stroke stroke-width stroke-opacity stroke-linecap stroke-linejoin stroke-dasharray stroke-dashoffset opacity transform text-anchor dominant-baseline font-family font-size font-weight font-style letter-spacing dx dy marker-start marker-mid marker-end markerWidth markerHeight refX refY orient markerUnits preserveAspectRatio gradientUnits gradientTransform offset stop-color stop-opacity spreadMethod version role aria-label'.split())
MATH_ARITY = {'mfrac': 2, 'mroot': 2, 'msup': 2, 'msub': 2, 'msubsup': 3, 'munder': 2, 'mover': 2, 'munderover': 3}
RAW_TEX = re.compile(r'\\(?:[A-Za-z]+|[\[\]()])|\$\$')


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def markup_errors(value, kind):
    """Accept static, self-contained XML only, using a deliberately small vocabulary."""
    if not nonempty(value):
        return [kind + '必须为非空XML字符串']
    if re.search(r'<!\s*(?:DOCTYPE|ENTITY)|<\?', value, re.I):
        return [kind + '不能含DOCTYPE、实体声明或处理指令']
    try:
        root = ET.fromstring(value)
    except (ET.ParseError, ValueError):
        return [kind + '不是完整、正确配对的XML']
    namespace, root_name, tags, attrs = (MATH_NS, 'math', MATH_TAGS, MATH_ATTRS) if kind == 'mathml' else (SVG_NS, 'svg', SVG_TAGS, SVG_ATTRS)
    if root.tag != '{' + namespace + '}' + root_name:
        return [kind + '根元素或命名空间不正确']
    errors, ids, references = [], set(), []
    for element in root.iter():
        if not isinstance(element.tag, str) or not element.tag.startswith('{' + namespace + '}'):
            errors.append(kind + '不允许混入其他命名空间或HTML元素')
            continue
        tag = element.tag.split('}', 1)[1]
        if tag not in tags:
            errors.append(kind + '不支持元素' + tag)
        for attribute, content in element.attrib.items():
            if attribute not in attrs:
                errors.append(kind + '不支持属性' + attribute)
            if re.search(r'url\s*\(', content, re.I):
                reference = re.fullmatch(r'url\(\s*#([A-Za-z_][A-Za-z0-9_.-]*)\s*\)', content)
                if kind != 'svg' or reference is None:
                    errors.append(kind + '不能引用外部资源或嵌入URL')
                else:
                    references.append(reference.group(1))
            if re.search(r'(?:javascript|https?|data)\s*:|@import|expression\s*\(', content, re.I):
                errors.append(kind + '属性不能包含外链、脚本或数据资源')
        if kind == 'mathml':
            if tag in MATH_ARITY and len(element) != MATH_ARITY[tag]:
                errors.append(f'mathml的{tag}必须恰有{MATH_ARITY[tag]}个子元素')
            if tag == 'math' and not len(element):
                errors.append('mathml必须含数学排版元素')
            if tag in {'mi', 'mn', 'mo', 'mtext'} and (len(element) or not nonempty(element.text)):
                errors.append('mathml的' + tag + '应为非空文字标记')
            if tag not in {'mi', 'mn', 'mo', 'mtext'} and nonempty(element.text):
                errors.append('mathml中的数学文字应放在mi、mn、mo或mtext中')
            if any(nonempty(child.tail) for child in element):
                errors.append('mathml中的运算符和文字不能散落在标记之间')
            if 'aria-label' in element.attrib and element is not root:
                errors.append('mathml的aria-label仅允许用于根math元素')
            if tag == 'mtable' and (not len(element) or any(child.tag != '{' + MATH_NS + '}mtr' for child in element)):
                errors.append('mathml的mtable应包含mtr行')
            if tag == 'mtr' and (not len(element) or any(child.tag != '{' + MATH_NS + '}mtd' for child in element)):
                errors.append('mathml的mtr应包含mtd单元格')
            if RAW_TEX.search(element.text or ''):
                errors.append('mathml不能含未渲染的LaTeX命令')
        else:
            identifier = element.get('id')
            if identifier is not None:
                if not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_.-]*', identifier) or identifier in ids:
                    errors.append('svg的id必须有效且不重复')
                ids.add(identifier)
    if kind == 'svg':
        try:
            bounds = [float(n) for n in re.split(r'[\s,]+', root.get('viewBox', '').strip())]
            if len(bounds) != 4 or not all(math.isfinite(n) for n in bounds) or bounds[2] <= 0 or bounds[3] <= 0:
                raise ValueError
        except ValueError:
            errors.append('svg必须含有效viewBox及正的宽高')
        if any(identifier not in ids for identifier in references):
            errors.append('svg的本地url(#id)必须引用图内存在的id')
    return errors


def validate_section_visuals(section, path, known_sources, lesson_sources):
    errors = []

    def source_errors(item, item_path):
        if 'source_ids' not in item:
            return
        refs = item['source_ids']
        if not isinstance(refs, list) or not refs or not all(nonempty(ref) for ref in refs):
            errors.append(item_path + '.source_ids必须为非空来源ID数组')
        elif len(refs) != len(set(refs)) or any(ref not in known_sources or ref not in lesson_sources for ref in refs):
            errors.append(item_path + '.source_ids必须引用本课已列出的有效来源且不重复')

    for field in ('formulas', 'diagrams'):
        if field not in section:
            continue
        entries = section[field]
        if not isinstance(entries, list):
            errors.append(path + '.' + field + '必须为数组')
            continue
        for index, item in enumerate(entries):
            p = f'{path}.{field}[{index}]'
            if not isinstance(item, dict):
                errors.append(p + '必须是对象')
                continue
            required = ('title', 'expression', 'explanation', 'conditions') if field == 'formulas' else ('title', 'svg', 'alt', 'caption')
            for name in required:
                if not nonempty(item.get(name)):
                    errors.append(p + '.' + name + '必须为非空字符串')
            if field == 'formulas':
                if isinstance(item.get('expression'), str) and RAW_TEX.search(item['expression']):
                    errors.append(p + '.expression需用可读Unicode，不能含未排版的LaTeX')
                variables = item.get('variables')
                if not isinstance(variables, list):
                    errors.append(p + '.variables必须为数组，无变量时可为空')
                else:
                    symbols = set()
                    for variable in variables:
                        if not isinstance(variable, dict) or not all(nonempty(variable.get(name)) for name in ('symbol', 'meaning', 'unit')):
                            errors.append(p + '.variables每项需symbol、meaning与unit；无量纲也须说明')
                        elif variable['symbol'] in symbols:
                            errors.append(p + '.variables的symbol不能重复')
                        else:
                            symbols.add(variable['symbol'])
                if 'mathml' in item:
                    errors.extend(p + '.' + error for error in markup_errors(item['mathml'], 'mathml'))
            elif nonempty(item.get('svg')):
                errors.extend(p + '.' + error for error in markup_errors(item['svg'], 'svg'))
            source_errors(item, p)
    return errors
