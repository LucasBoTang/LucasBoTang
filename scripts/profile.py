"""Generate self-contained profile figures from GitHub data. No hosted widgets."""
import argparse
import datetime as dt
import html
import json
from pathlib import Path
import subprocess

from fontTools.ttLib import TTFont
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen

ROOT = Path(__file__).resolve().parents[1]
LOGIN = 'LucasBoTang'


def api(endpoint, query=None):
    command = ['gh', 'api', endpoint]
    if query:
        command += ['-f', 'query=' + query]
    result = json.loads(subprocess.check_output(command, text=True, encoding='utf-8'))
    if isinstance(result, dict) and result.get('errors'):
        raise RuntimeError(result['errors'])
    return result


def collect():
    user = api(f'users/{LOGIN}')
    repos = []
    page = 1
    while True:
        batch = api(f'users/{LOGIN}/repos?type=owner&per_page=100&page={page}')
        repos.extend(batch)
        if len(batch) < 100:
            break
        page += 1
    original = [r for r in repos if not r['fork'] and not r['private']]
    query = '''query { user(login: "LucasBoTang") { contributionsCollection {
      contributionCalendar { totalContributions weeks { contributionDays {
        date contributionCount contributionLevel
      } } }
    } } }'''
    calendar = api('graphql', query)['data']['user']['contributionsCollection']['contributionCalendar']
    data = {
        'updated': dt.datetime.now(dt.timezone.utc).isoformat(),
        'followers': user['followers'],
        'repositories': len(original),
        'stars': sum(r['stargazers_count'] for r in original),
        'calendar': calendar,
    }
    # Store only public aggregates, never credentials or private repository metadata.
    (ROOT / 'assets/data.json').write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')
    return data


FONTS = {}
for name in ('geist', 'geist-mono', 'bodoni-moda'):
    font = TTFont(ROOT / f'fonts/{name}.woff2')
    FONTS[name] = (font, font.getGlyphSet(location={'wght': 400, 'opsz': 48}))


def text(x, y, value, size=16, color='#eeeef0', font='geist', anchor='start'):
    """Outline type so GitHub SVG image rendering preserves the website's fonts."""
    value = str(value)
    face, glyphs = FONTS[font]
    cmap = face.getBestCmap()
    scale = size / face['head'].unitsPerEm
    names = [cmap.get(ord(c), '.notdef') for c in value]
    width = sum(glyphs[n].width for n in names) * scale
    if anchor == 'end':
        x -= width
    elif anchor == 'middle':
        x -= width / 2
    pen = SVGPathPen(glyphs)
    for name in names:
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, y)))
        x += glyphs[name].width * scale
    return f'<g aria-label="{html.escape(value, quote=True)}"><title>{html.escape(value)}</title><path fill="{color}" d="{pen.getCommands()}"/></g>'


def line(x1, y1, x2, y2, color, opacity=1):
    return f'<path d="M{x1},{y1}H{x2}" stroke="{color}" opacity="{opacity}"/>' if y1 == y2 else f'<path d="M{x1},{y1}L{x2},{y2}" stroke="{color}" opacity="{opacity}"/>'


def rect(x, y, w, h, color, rx=0):
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{color}"/>'


def palette(mode):
    if mode == 'dark':
        return dict(bg='#101113', fg='#eeeef0', muted='#a3a7ad', rule='#2c3035', accent='#91afd2',
                    levels=['#24282e', '#263b64', '#3c70a2', '#3e9eb2', '#a8cbd4'],
                    bars=['#91afd2', '#78beb7', '#3e9eb2', '#6e8db8', '#97b5a8', '#87929e'])
    return dict(bg='#f7f8fa', fg='#202b39', muted='#586779', rule='#d9e0e7', accent='#3c70a2',
                levels=['#e1e7ee', '#a8cbd4', '#78beb7', '#3e9eb2', '#263b64'],
                bars=['#3c70a2', '#3d837e', '#257b90', '#586f98', '#58796a', '#687582'])


def save(name, width, height, title, desc, elements, p):
    content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}" role="img" aria-labelledby="title desc">
<title id="title">{html.escape(title)}</title><desc id="desc">{html.escape(desc)}</desc>
{rect(0, 0, width, height, p['bg'], 8)}
{''.join(elements)}
</svg>'''
    (ROOT / f'assets/{name}.svg').write_text(content, encoding='utf-8')


def render(data):
    days = [d for w in data['calendar']['weeks'] for d in w['contributionDays']]
    assert sum(d['contributionCount'] for d in days) == data['calendar']['totalContributions']
    date = data['updated'][:10]
    for mode in ('dark', 'light'):
        p = palette(mode)
        # All four links use the same 18px icon grid, stroke and outlined Geist label.
        icons = {
            'website': ('Website', 92, '<circle cx="9" cy="9" r="8"/><ellipse cx="9" cy="9" rx="3.5" ry="8"/><path d="M1 9h16"/>'),
            'research': ('Research', 102, '<path d="m4 4 10 1M4 4l4 10m6-9-6 9"/><circle cx="4" cy="4" r="2.3"/><circle cx="14" cy="5" r="2.3"/><circle cx="8" cy="14" r="2.3"/>'),
            'scholar': ('Scholar', 90, '<path d="m1 7 8-4 8 4-8 4-8-4Zm3 2v5q5 4 10 0V9m3-2v7"/>'),
            'email': ('Email', 76, '<rect x="1" y="3" width="16" height="12" rx="2"/><path d="m2 4 7 6 7-6"/>'),
        }
        for name, (label, width, icon) in icons.items():
            svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="32" viewBox="0 0 {width} 32" role="img" aria-label="{label}">'
                   f'<title>{label}</title><g transform="translate(0 7)" fill="none" stroke="{p["accent"]}" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round">{icon}</g>'
                   + text(25, 21, label, 14, p['accent']) + '</svg>')
            (ROOT / f'assets/link-{name}-{mode}.svg').write_text(svg, encoding='utf-8')
        for mobile in (False, True):
            width = 440 if mobile else 880
            pad = 24 if mobile else 36
            suffix = f'{mode}' + ('-mobile' if mobile else '')
            t = lambda x, y, value, size=16, color=None, font='geist', anchor='start': text(x, y, value, size, color or p['fg'], font, anchor)
            # The personal site's typographic signature, without duplicating project pins.
            e = [t(pad, 90, 'Bo Tang', 72 if mobile else 88, font='bodoni-moda'),
                 t(pad, 130, 'Operations research & machine learning', 16 if mobile else 21, p['muted'])]
            for j in range(3):
                e.append(rect(width - pad - 36 + j * 12, 38, 5, 14, p['accent']))
            save(f'header-{suffix}', width, 164, 'Bo Tang', 'Operations research and machine learning.', e, p)

            # GitHub's actual daily contribution counts, coloured using research figure tones.
            height = 395 if mobile else 375
            e = [t(pad, 45, 'Open-source activity', 25 if mobile else 29, font='bodoni-moda')]
            metrics = [(data['calendar']['totalContributions'], 'Contributions'),
                       (data['stars'], 'Stars received'), (data['repositories'], 'Original repos')]
            col = (width - 2 * pad) / 3
            for i, (value, label) in enumerate(metrics):
                x = pad + i * col
                e += [t(x, 100, f'{value:,}', 30 if mobile else 38, p['accent'], 'geist-mono'),
                      t(x, 125, label, 12 if mobile else 15, p['muted'])]
            e.append(line(pad, 146, width - pad, 146, p['rule']))
            e.append(t(pad, 172, 'Contributions / past year', 13, p['muted'], 'geist-mono'))
            weeks = data['calendar']['weeks']
            step = (width - pad * 2) / len(weeks)
            cell = step - (2 if mobile else 3)
            grid_y = 211
            seen_month = None
            levels = ['NONE', 'FIRST_QUARTILE', 'SECOND_QUARTILE', 'THIRD_QUARTILE', 'FOURTH_QUARTILE']
            for wi, week in enumerate(weeks):
                first = dt.date.fromisoformat(week['contributionDays'][0]['date'])
                if first.month != seen_month:
                    if wi < len(weeks) - 3 and (not mobile or first.month % 2 == 1):
                        e.append(t(pad + wi * step, 198, first.strftime('%b'), 10 if mobile else 12, p['muted'], 'geist-mono'))
                    seen_month = first.month
                for day in week['contributionDays']:
                    when = dt.date.fromisoformat(day['date'])
                    row = (when.weekday() + 1) % 7
                    level = levels.index(day['contributionLevel'])
                    e.append(f'<g><title>{day["date"]}: {day["contributionCount"]} contributions</title>' +
                             rect(round(pad + wi * step, 2), round(grid_y + row * step, 2), round(cell, 2), round(cell, 2), p['levels'][level], 1) + '</g>')
            legend_y = 282 if mobile else 352
            e.append(t(pad, legend_y, 'Less', 11, p['muted'], 'geist-mono'))
            for i, color in enumerate(p['levels']):
                e.append(rect(pad + 37 + i * 14, legend_y - 10, 10, 10, color, 1))
            e.append(t(pad + 114, legend_y, 'More', 11, p['muted'], 'geist-mono'))
            if mobile:
                e += [t(pad, 320, f'{days[0]["date"]} — {days[-1]["date"]}', 12, p['muted'], 'geist-mono'),
                      t(pad, 346, 'Stars & repos: owned public non-forks.', 12, p['muted']),
                      t(pad, 372, f'Updated {date} UTC', 11, p['muted'], 'geist-mono')]
            else:
                e.append(t(width - pad, 352, f'{days[0]["date"]} — {days[-1]["date"]}', 11, p['muted'], 'geist-mono', 'end'))
            save(f'activity-{suffix}', width, height, 'GitHub activity',
                 f'{data["calendar"]["totalContributions"]} contributions in the past year. {data["stars"]} stars across {data["repositories"]} owned public non-fork repositories. Updated {date} UTC.', e, p)



if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--refresh', action='store_true')
    args = parser.parse_args()
    data = collect() if args.refresh else json.loads((ROOT / 'assets/data.json').read_text(encoding='utf-8'))
    render(data)
    print(f'Generated 16 SVG assets from GitHub data updated {data["updated"]}.')
