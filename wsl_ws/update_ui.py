# -*- coding: utf-8 -*-
import sys
import re

f = 'gemini_web_gui/src/App.tsx'
with open(f, 'r', encoding='utf-8') as file:
    content = file.read()

# 1. Add examples when messages is empty
empty_state_old = """
              ))}
              <div ref={chatEndRef} />
"""

empty_state_new = """
              ))}
              {messages.length === 0 && (
                <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.textMuted, gap: 16 }}>
                  <div style={{ fontSize: 16, fontWeight: 600, color: C.white, marginTop: 40 }}>Welcome to Gemini Robotics ER</div>
                  <div style={{ fontSize: 13, maxWidth: 400, textAlign: 'center', lineHeight: 1.5 }}>
                    I can orchestrate 3 Franka arms to build towers and organize objects. Try an example command:
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 8, width: '100%', maxWidth: 480 }}>
                    {[
                      "Build a 3-layer tower with the red cube as the base, green cylinder in the middle, and blue cube on top.",
                      "Move all the cubes to the center target table.",
                      "Stack the yellow cylinder and lime cube on top of the blue cube."
                    ].map((example, i) => (
                      <div key={i} onClick={() => setText(example)} style={{ background: C.bgInput, padding: '12px 16px', borderRadius: 12, border: `1px solid ${C.border}`, fontSize: 13, color: C.text, cursor: 'pointer' }}>
                        {example}
                      </div>
                    ))}
                  </div>
                </div>
              )}
              <div ref={chatEndRef} />
"""
content = content.replace(empty_state_old.strip('\n'), empty_state_new.strip('\n'))

# 2. Add made by m9g
footer_old = """
            <div style={{ maxWidth: 720, margin: '6px auto 0', fontSize: 10, color: C.textMuted, textAlign: 'center' }}>
              Gemini Robotics ER controls 3 Franka FR3 arms via Isaac Sim
            </div>
"""
footer_new = """
            <div style={{ maxWidth: 720, margin: '8px auto 0', fontSize: 11, color: C.textMuted, textAlign: 'center', lineHeight: 1.4 }}>
              Gemini Robotics ER controls 3 Franka FR3 arms via Isaac Sim.<br/>
              Made by <a href="https://mincasurong.ai.studio/" target="_blank" rel="noreferrer" style={{ color: C.blue, textDecoration: 'none' }}>m9g</a>
            </div>
"""
content = content.replace(footer_old.strip('\n'), footer_new.strip('\n'))

with open(f, 'w', encoding='utf-8') as file:
    file.write(content)
print("Updated App.tsx successfully.")
