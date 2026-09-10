"""Landing page for the machine's running workspace Runtimes."""

from html import escape
from pathlib import Path
from urllib.parse import urlsplit


def _display_path(path: str) -> str:
    """A workspace path, with the user's home directory abridged to `~`.

    Reading `~/.promptaflow/...` as `/Users/name/.promptaflow/...` tells the operator
    nothing the abridged form doesn't, and a long home path eats the column.
    The separator is checked rather than assumed, by comparing against a
    normalized home and trusting the user's own home to be absolute.
    """

    home = str(Path.home())
    if path == home:
        return "~"
    for separator in ("/", "\\"):
        if path.startswith(home + separator):
            return "~" + path[len(home):]
    return path


def render_hub_ui(
    runtimes: list[dict[str, str]], shutdown_token: str | None = None,
) -> str:
    rows = []
    for runtime in runtimes:
        path = escape(_display_path(runtime['path']))
        url = escape(runtime['url'], quote=True)
        port = urlsplit(runtime['url']).port
        rows.append(f'<tr><td><code>{path}</code></td><td><span class="status">运行中</span></td>'
                    f'<td><code>{port}</code></td><td><a href="{url}">打开 UI ↗</a></td></tr>')
    content = ('<div class="table"><table><thead><tr><th>Workspace 路径</th><th>状态</th>'
               '<th>UI 端口</th><th>入口</th></tr></thead><tbody>' + ''.join(rows) + '</tbody></table></div>') if rows else (
                   '<div class="empty">暂无运行中的 Runtime。<p>启动项目的 PromptaFlow 服务后，刷新此页即可看到入口。</p></div>')
    shutdown_control = ""
    if shutdown_token is not None:
        shutdown_control = f'''<button class="shutdown" id="shutdown" type="button">关闭 PromptaFlow</button>
<script>
const shutdown = document.getElementById('shutdown');
shutdown.addEventListener('click', async () => {{
  if (!window.confirm('将结束本 Hub 启动的 Runtime 及其执行 Worker，然后关闭 Hub。其它来源启动的 Runtime 不受影响。正在运行的工作会被中断，确定继续吗？')) return;
  shutdown.disabled = true;
  shutdown.textContent = '正在关闭…';
  try {{
    const response = await fetch('/api/v1/hub/shutdown', {{
      method: 'POST',
      headers: {{'x-promptaflow-shutdown-token': {shutdown_token!r}}},
    }});
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || '关闭失败');
    document.querySelector('main').innerHTML = '<div class="finished"><h1>PromptaFlow 已关闭</h1><p>所有 Runtime 的关闭请求已发送，Hub 正在退出。现在可以关闭此页面。</p></div>';
  }} catch (error) {{
    shutdown.disabled = false;
    shutdown.textContent = '关闭 PromptaFlow';
    window.alert(`无法关闭 PromptaFlow：${{error.message || error}}`);
  }}
}});
</script>'''
    return '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>PromptaFlow Hub</title>
<style>
:root{color-scheme:light dark;--bg:#ffffff;--panel:#ffffff;--text:#20242c;--muted:#637083;--line:#e3e7ec;--link:#315fc9;--brand:#2563eb;--brand-end:#b45309;--mark-bg:#f7f8fb;--mark-line:#e4e8f0;--control-bg:#f1f3f8;--control-raised:#e4e8f0;--control-fg:#171a21;--danger:#b42318;--danger-bg:#fff1f0;--danger-raised:#ffe4e1}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.6 system-ui,sans-serif}
main{max-width:1120px;margin:64px auto;padding:0 24px}header{display:flex;align-items:center;justify-content:space-between;gap:24px}
.brand{display:flex;align-items:center;gap:12px}.mark{display:block;width:32px;height:32px;flex:none}.mark .plate{fill:var(--mark-bg);stroke:var(--mark-line)}.mark .flow{fill:none;stroke:var(--brand);stroke-width:1.8;stroke-linecap:round;stroke-linejoin:round}.mark .terminal{fill:var(--brand-end)}h1{font-size:30px;margin:0;letter-spacing:-1px}.sub{color:var(--muted);margin:8px 0 30px}a{color:var(--link);text-decoration:none}a:hover{text-decoration:underline}a:focus-visible{outline:2px solid var(--link);outline-offset:5px}
.actions{display:flex;align-items:center;gap:8px}.refresh,.shutdown{border:0;padding:8px 12px;border-radius:12px;font-size:13px;font-weight:600;cursor:pointer;white-space:nowrap}.refresh{background:var(--control-bg);color:var(--control-fg)}.refresh:hover{background:var(--control-raised);text-decoration:none}.shutdown{background:var(--danger-bg);color:var(--danger)}.shutdown:hover{background:var(--danger-raised)}.shutdown:disabled{cursor:wait;opacity:.65}
.table{overflow:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel);padding:0 20px}table{border-collapse:collapse;width:100%;text-align:left}th{font-size:12px;color:var(--muted);font-weight:500}th,td{padding:18px 2px;border-bottom:1px solid var(--line)}tbody tr:last-child td{border-bottom:0}td:first-child{min-width:250px;overflow-wrap:anywhere}td:not(:first-child){white-space:nowrap}code{font:13px/1.6 ui-monospace,monospace}.status{color:#258353;font-size:13px}.status:before{content:'●';margin-right:7px;font-size:10px}.empty{background:var(--panel);border:0;padding:48px 24px;border-radius:12px;text-align:center}.empty p,footer{color:var(--muted);font-size:13px}footer{margin-top:20px}
@media(prefers-color-scheme:dark){:root{--bg:#181818;--panel:#181818;--text:#edf0f5;--muted:#9aa6b7;--line:#303641;--link:#91b2ff;--brand:#adc6ff;--brand-end:#ffb786;--mark-bg:#212121;--mark-line:#2a2d35;--control-bg:#2a2a2a;--control-raised:#333333;--control-fg:#e1e2ec;--danger:#ffaaa4;--danger-bg:#3b201f;--danger-raised:#512725}.status{color:#75c99c}}
@media(max-width:600px){main{margin:28px auto;padding:0 16px}.table{padding:0 14px}th,td{padding:14px 2px}h1{font-size:26px}}
</style></head><body><main><header><div class="brand"><svg class="mark" viewBox="0 0 20 20" aria-hidden="true" focusable="false"><rect class="plate" x="0.5" y="0.5" width="19" height="19" rx="5"/><path class="flow" d="M5.5 15.5v-11h4.6c3 0 5 1.9 5 4.5s-2 4.5-5 4.5H5.5M9.8 9c3.5 0 3.5 6.5 6.2 6.5"/><circle class="terminal" cx="16" cy="15.5" r="1.7"/></svg><h1>PromptaFlow Hub</h1></div><div class="actions"><a class="refresh" href="/ui">刷新列表</a>''' + shutdown_control + '''</div></header>
''' + f'<p class="sub">{len(runtimes)} 个运行中的 Runtime · 选择工作区进入 UI</p>' + content + '''
<footer>列表仅检查运行中的服务。端口可能在重启后变化，请收藏此 Hub 页面。</footer>
</main></body></html>'''
