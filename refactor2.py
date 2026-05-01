import os

def main():
    with open('frontend/src/App.jsx', 'r', encoding='utf-8') as f:
        content = f.read()

    # Define the sections and their start strings
    # We will slice the string by finding the start of each section, and the start of the next section
    
    markers = [
        ('{/* MAIN GRID */}', 'main_start'),
        ('{/* Portfolio Performance */}', 'portfolio'),
        ('{/* TradingView Candlestick Chart */}', 'chart'),
        ('{/* Open Positions */}', 'open_pos'),
        ('{/* RIGHT SIDEBAR */}', 'right_sidebar_start'),
        ('<ManualTradeTerminal', 'manual'),
        ('{/* Strategy Brain */}', 'strategy'),
        ('{/* System Health */}', 'health'),
        ('{/* Signal Analysis */}', 'signal'),
        ('{/* Risk Dashboard */}', 'risk'),
        ('{/* Analytics */}', 'analytics'),
        ('{/* Trade Ledger */}', 'ledger'),
        ('{/* ALGORITHMIC FEED */}', 'algo'),
        ('</div>\n    </div>\n  );\n}\n\nexport default App;', 'end')
    ]

    # Find the positions
    positions = []
    for marker, name in markers:
        pos = content.find(marker)
        if pos != -1:
            positions.append((pos, name))
            
    positions.sort(key=lambda x: x[0])
    
    sections = {}
    for i in range(len(positions) - 1):
        pos_start, name = positions[i]
        pos_end, _ = positions[i+1]
        
        # Extract
        part = content[pos_start:pos_end]
        
        # Cleanup extra closing divs if they belong to the layout
        if name == 'open_pos':
            # It has '</div>\n        </div>\n\n        {/* RIGHT SIDEBAR */}'
            part = part.rsplit('</div>\n        </div>', 1)[0]
        elif name == 'ledger':
            # It has '</div>\n        </div>\n      </div>\n\n      {/* ALGORITHMIC FEED */}'
            part = part.rsplit('</div>\n        </div>\n      </div>', 1)[0]
        
        sections[name] = part.strip()
        
    # Reassemble
    
    new_layout = f"""      {{/* MAIN GRID */}}
      <div className="main-grid">
        
        {{/* LEFT SIDEBAR: Stats & Performance */}}
        <div className="side-stack left-sidebar">
{sections.get('portfolio', '')}

{sections.get('signal', '')}

{sections.get('health', '')}
        </div>

        {{/* CENTER CONTENT: Charts & Visuals */}}
        <div className="side-stack center-content">
{sections.get('chart', '')}

{sections.get('open_pos', '')}

{sections.get('ledger', '')}
        </div>

        {{/* RIGHT SIDEBAR: Controls & Strategy */}}
        <div className="side-stack right-sidebar">
{sections.get('manual', '')}

{sections.get('strategy', '')}

{sections.get('risk', '')}

{sections.get('analytics', '')}

{sections.get('algo', '')}
        </div>
      </div>"""

    # Get the header and footer
    header = content[:positions[0][0]]
    footer = content[positions[-1][0]:]
    
    new_content = header + new_layout + '\n' + footer
    
    with open('frontend/src/App.jsx', 'w', encoding='utf-8') as f:
        f.write(new_content)

if __name__ == '__main__':
    main()
