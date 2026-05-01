import re

def main():
    with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
        content = f.read()

    # Find where <div className="main-grid"> starts
    grid_start = content.find('{/* MAIN GRID */}')
    algo_end = content.find('</div>\n    </div>\n  );\n}')

    if grid_start == -1 or algo_end == -1:
        print("Could not find start/end")
        return

    # To be safe, I'll just write the entire new App.jsx
    # I can use regex to extract each panel precisely because they have comments above them.
    
    def extract_panel(start_comment, end_comment=None, end_regex=None):
        start = content.find(start_comment)
        if start == -1: return ""
        
        if end_comment:
            end = content.find(end_comment, start)
            if end != -1: return content[start:end].strip()
            
        if end_regex:
            match = re.search(end_regex, content[start:])
            if match:
                return content[start:start+match.start()].strip()
                
        return ""

    portfolio = extract_panel('{/* Portfolio Performance */}', '{/* TradingView Candlestick Chart */}')
    chart = extract_panel('{/* TradingView Candlestick Chart */}', '{/* Open Positions */}')
    open_pos = extract_panel('{/* Open Positions */}', '{/* RIGHT SIDEBAR */}')
    # Remove extra closing divs from open_pos
    if open_pos.endswith('</div>\n        </div>'):
        open_pos = open_pos[:-18].strip()

    manual = extract_panel('{/* RIGHT SIDEBAR */}\n        <div className="side-stack">\n          <ManualTradeTerminal', '{/* Strategy Brain */}')
    if manual:
        # cleanup
        manual = "<ManualTradeTerminal" + manual.split('<ManualTradeTerminal')[1]

    strategy = extract_panel('{/* Strategy Brain */}', '{/* System Health */}')
    health = extract_panel('{/* System Health */}', '{/* Signal Analysis */}')
    signal = extract_panel('{/* Signal Analysis */}', '{/* Risk Dashboard */}')
    risk = extract_panel('{/* Risk Dashboard */}', '{/* Analytics */}')
    analytics = extract_panel('{/* Analytics */}', '{/* Trade Ledger */}')
    ledger = extract_panel('{/* Trade Ledger */}', '{/* ALGORITHMIC FEED */}')
    
    if ledger.endswith('</div>\n        </div>\n      </div>'):
        ledger = ledger[:-30].strip()

    algo = extract_panel('{/* ALGORITHMIC FEED */}', '</div>\n    </div>\n  );\n}')
    
    # Now construct the new layout
    new_layout = f"""      {{/* MAIN GRID */}}
      <div className="main-grid">
        
        {{/* LEFT SIDEBAR: Stats & Performance */}}
        <div className="side-stack left-sidebar">
          {portfolio}

          {signal}

          {health}
        </div>

        {{/* CENTER CONTENT: Charts & Visuals */}}
        <div className="side-stack center-content">
          {chart}

          {open_pos}

          {ledger}
        </div>

        {{/* RIGHT SIDEBAR: Controls & Strategy */}}
        <div className="side-stack right-sidebar">
          {manual}

          {strategy}

          {risk}

          {analytics}

          {algo}
        </div>
      </div>"""

    new_content = content[:grid_start] + new_layout + '\n' + content[algo_end:]
    
    with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
        f.write(new_content)
        print("Updated App.jsx successfully!")

if __name__ == '__main__':
    main()
