# UWB Pose Game — Research Findings & Recommendations

## Quick Decision: Unity MCP vs Browser (p5.js)

### Unity MCP Path
- **Cost:** Free (MIT license). Unity Editor is free for revenue under $200k.
- **MCPs available:** CoplayDev/unity-mcp (5.6k stars), CoderGamester/mcp-unity (~1k stars), IvanMurzak/Unity-MCP (~500 stars).
- **What Unity MCP does:** Claude Code can create GameObjects, write C# scripts, manage scenes, build projects — all via natural language prompts in your terminal.
- **The catch:** Active bugs filed Jan-Feb 2026 (connection drops, session issues on Issues #643 and #664). Requires Unity installed + Node.js + MCP config. You still need to understand Unity concepts (GameObjects, MonoBehaviours, Update loop, threading) to debug issues. Getting external WebSocket data into Unity requires thread marshaling. Setup realistically takes 1-2 days even with MCP help.
- **Verdict for your week:** NOT recommended as primary path. Too much setup overhead when neither person knows Unity. Save for v2 after the project week.

### Browser (p5.js) Path
- **Cost:** Free. Zero install.
- **What you need:** A text editor and a browser.
- **Why it wins:** Claude Code writes HTML/JS natively with zero friction. WebSocket is built into browsers. Drawing stick figures is trivial. Save file → refresh browser → see changes instantly. Both teammates can work simultaneously without syncing project files. Demo mode with mouse means you can develop and test the game entirely without hardware.
- **Verdict:** RECOMMENDED for this week. Fastest path to a working, polished game.

### Upgrade Path to Unity Later
After the project week, if you want to upgrade to 3D:
```
# In Unity: Window > Package Manager > + > Add package from git URL
https://github.com/CoplayDev/unity-mcp.git

# In terminal:
claude mcp add --scope user --transport stdio coplay-mcp -- uvx --python ">=3.11" coplay-mcp-server@latest
```
Then tell Claude Code: "Port my pose game from p5.js to Unity with 3D stick figures and particle effects."

---

## Key Repos

### Firmware / UWB
| Repo | What | Why It Matters |
|------|------|----------------|
| github.com/Makerfabs/Makerfabs-ESP32-UWB-DW3000 | Official DW3000 library. You likely already use this. | Starting point. BUT: does NOT support time-multiplexing for multiple tags. |
| github.com/kk9six/dw3000 | One tag + multiple anchors, optimized TWR protocol. | Best multi-anchor firmware base. Extend this for TDMA. |
| github.com/Fhilb/DW3000_Arduino | Cleaner alternative DW3000 library. | Fallback if Makerfabs lib gives trouble. |
| github.com/KunYi/esp32-uwb-positioning-system | Full system: firmware + Python viz + tag simulator. | Use the tag simulator to test your game without hardware. |
| github.com/realzoulou/esphome-uwb-dw3000 | ESPHome component with calibration docs. | Best antenna delay calibration reference. |

### Signal Smoothing
| Repo | What |
|------|------|
| github.com/casiez/OneEuroFilter | Original 1€ Filter. Adaptive low-pass for noisy real-time signals. |
| github.com/dli7319/one-euro-filter-js | JavaScript port. Drop into your HTML file. |

### MCPs to Install for Claude Code
| MCP | What | Install Command |
|-----|------|-----------------|
| Context7 | Live library docs (p5.js, Arduino, etc.) | `claude mcp add context7 -- npx -y @context7/mcp@latest` |
| GitHub MCP | Browse repos directly | `claude mcp add github -- npx -y @anthropic-ai/mcp-github` |
| Filesystem | Read/write project files | Built into Claude Code already |

### MCPs to Skip
| MCP | Why |
|-----|-----|
| CoplayDev/unity-mcp | Great tool, wrong timeline. Active connection bugs. |
| DG1001/webserial-mcp | For MicroPython. You use Arduino IDE. |
| navado/ESP32MCPServer | For LLMs controlling IoT, not game data streaming. |

---

## Architecture

```
ESP32 Tags (up to 3)       Python Bridge              Browser Game
┌──────────┐  UDP @ 20Hz   ┌─────────────┐  WebSocket  ┌──────────┐
│ Tag 1    │──────────────→│             │────────────→│          │
│ Tag 2    │──────────────→│  bridge.py  │             │  p5.js   │
│ Tag 3    │──────────────→│             │←────────────│  game    │
└──────────┘               └─────────────┘             └──────────┘
      ↕ TWR                                            1€ filter
┌──────────┐                                           in browser
│ 4 Anchors│
└──────────┘
```

---

## Critical Warnings

1. **Makerfabs library does NOT support time-multiplexing.** Their product page says so explicitly. Implement TDMA yourself or use kk9six/dw3000.
2. **Antenna delay calibration takes time.** Value 16350 worked for one builder. Check realzoulou repo for calibration docs.
3. **Raw UWB is noisy.** Median filter on ESP32 + 1€ filter on game side. Expect 10-15cm accuracy.
4. **WiFi interferes with ranging.** Keep UDP packets tiny.
5. **Unity MCP has active bugs.** Connection drops reported Jan-Feb 2026. Works but expect debugging.
