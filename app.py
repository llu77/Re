"""
مستشار التأهيل البصري — واجهة المستخدم
Vision Rehab AI Consultant — Streamlit UI
==========================================
"""

import os
import json
import base64
import time
import anthropic
import streamlit as st
from datetime import datetime
from utils.security import sanitize_patient_input, validate_medical_output
from rehab_consultant import SYSTEM_PROMPT, TOOLS, execute_tool, extract_text_response
from cdss import run_cdss_evaluation

# ═══════════════════════════════════════════════════════════════
# Page Config — يجب أن يكون أول شيء في الملف
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="مستشار التأهيل البصري الذكي",
    page_icon="👁️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════
# Custom CSS — التصميم الاحترافي الكامل
# ═══════════════════════════════════════════════════════════════

CUSTOM_CSS = """
<style>
/* ── Google Fonts ── */
@import url('https://fonts.googleapis.com/css2?family=Cairo:wght@300;400;500;600;700;800;900&family=Tajawal:wght@300;400;500;700;800&display=swap');

/* ── Design Tokens ── */
:root {
    --primary:        #1E3A5F;
    --primary-light:  #2E5B8C;
    --secondary:      #2E8BC0;
    --secondary-light:#4FA8D8;
    --accent:         #0B8457;
    --accent-light:   #10A567;
    --bg:             #EEF2F7;
    --card:           #FFFFFF;
    --text:           #1A2744;
    --text-sub:       #4A5568;
    --text-muted:     #718096;
    --border:         #E2E8F0;
    --border-focus:   #2E8BC0;
    --shadow-sm:      0 1px 3px rgba(0,0,0,0.08), 0 1px 2px rgba(0,0,0,0.04);
    --shadow:         0 4px 6px -1px rgba(0,0,0,0.07), 0 2px 4px -1px rgba(0,0,0,0.04);
    --shadow-md:      0 10px 25px -5px rgba(0,0,0,0.08), 0 4px 10px -5px rgba(0,0,0,0.04);
    --shadow-lg:      0 20px 40px -10px rgba(0,0,0,0.1);
    --radius-sm:      8px;
    --radius:         12px;
    --radius-lg:      20px;
    --radius-xl:      28px;
}

/* ── Base Reset ── */
*, *::before, *::after { box-sizing: border-box; }

html, body, .stApp, [class*="css"] {
    font-family: 'Cairo', 'Tajawal', -apple-system, sans-serif !important;
    direction: rtl;
}

.stApp {
    background: var(--bg) !important;
}

/* ── Hide Streamlit chrome ── */
#MainMenu, footer, header,
.stDeployButton,
[data-testid="stToolbar"],
[data-testid="stDecoration"],
[data-testid="stStatusWidget"] {
    display: none !important;
}

/* ════════════════════════════════════
   SIDEBAR
   ════════════════════════════════════ */
[data-testid="stSidebar"] {
    background: linear-gradient(170deg, #142540 0%, #1E3A5F 60%, #1A3252 100%) !important;
    border-left: 1px solid rgba(255,255,255,0.06) !important;
    min-width: 280px !important;
}

[data-testid="stSidebar"] > div:first-child {
    padding: 0 !important;
}

[data-testid="stSidebar"] .block-container {
    padding: 0 !important;
}

/* ── Sidebar Header ── */
.sb-header {
    background: linear-gradient(135deg, rgba(46,139,192,0.25) 0%, rgba(11,132,87,0.15) 100%);
    border-bottom: 1px solid rgba(255,255,255,0.08);
    padding: 28px 20px 22px;
    text-align: center;
}

.sb-logo {
    font-size: 54px;
    display: block;
    margin-bottom: 12px;
    filter: drop-shadow(0 4px 12px rgba(0,0,0,0.4));
    animation: floatLogo 4s ease-in-out infinite;
}
@keyframes floatLogo {
    0%,100% { transform: translateY(0); }
    50%      { transform: translateY(-6px); }
}

.sb-title {
    color: #FFFFFF;
    font-size: 15px;
    font-weight: 800;
    margin: 0 0 4px;
    letter-spacing: -0.3px;
}

.sb-subtitle {
    color: rgba(255,255,255,0.45);
    font-size: 10px;
    font-weight: 500;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    margin: 0;
}

.sb-model-badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    margin-top: 10px;
    padding: 4px 10px;
    background: rgba(46,139,192,0.25);
    border: 1px solid rgba(46,139,192,0.4);
    border-radius: 20px;
    font-size: 10px;
    color: #60C4F0;
    font-weight: 600;
}

/* ── Sidebar Body ── */
.sb-body {
    padding: 16px 14px;
}

/* ── Section Label ── */
.sb-section-label {
    color: rgba(255,255,255,0.35);
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 2px;
    text-transform: uppercase;
    margin: 18px 0 8px 4px;
}

/* ── Stat Grid ── */
.sb-stats {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
    margin-bottom: 4px;
}

.sb-stat {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: var(--radius-sm);
    padding: 12px 8px;
    text-align: center;
    transition: background 0.2s;
}
.sb-stat:hover { background: rgba(255,255,255,0.1); }

.sb-stat-num {
    color: #60C4F0;
    font-size: 22px;
    font-weight: 900;
    line-height: 1;
    display: block;
}
.sb-stat-lbl {
    color: rgba(255,255,255,0.45);
    font-size: 9px;
    font-weight: 500;
    display: block;
    margin-top: 4px;
}

/* ── Tool Chips ── */
.tool-chip {
    display: flex;
    align-items: center;
    gap: 9px;
    padding: 8px 10px;
    background: rgba(255,255,255,0.05);
    border: 1px solid rgba(255,255,255,0.07);
    border-radius: var(--radius-sm);
    margin-bottom: 5px;
    transition: all 0.2s;
    cursor: default;
}
.tool-chip:hover {
    background: rgba(255,255,255,0.09);
    border-color: rgba(255,255,255,0.14);
    transform: translateX(-2px);
}
.tool-chip-icon { font-size: 13px; width: 18px; text-align: center; flex-shrink: 0; }
.tool-chip-name { color: rgba(255,255,255,0.75); font-size: 11px; font-weight: 500; flex: 1; }
.tool-chip-badge {
    font-size: 8px;
    padding: 2px 6px;
    border-radius: 10px;
    font-weight: 700;
    background: rgba(16,185,129,0.18);
    color: #34D399;
    border: 1px solid rgba(16,185,129,0.25);
}

/* ── Sidebar Divider ── */
.sb-divider {
    height: 1px;
    background: rgba(255,255,255,0.07);
    margin: 14px 0;
}

/* ── Clear Chat Button (sidebar) ── */
[data-testid="stSidebar"] .stButton > button {
    font-family: 'Cairo', sans-serif !important;
    background: rgba(220, 38, 38, 0.12) !important;
    color: rgba(252, 165, 165, 0.9) !important;
    border: 1px solid rgba(220, 38, 38, 0.25) !important;
    border-radius: var(--radius-sm) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    width: 100% !important;
    padding: 8px 16px !important;
    transition: all 0.2s !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(220, 38, 38, 0.22) !important;
    border-color: rgba(220, 38, 38, 0.4) !important;
    transform: none !important;
}

/* ════════════════════════════════════
   MAIN CONTENT
   ════════════════════════════════════ */
.main .block-container {
    max-width: 900px !important;
    padding: 0 24px 24px !important;
    margin: 0 auto !important;
}

/* ── Page Header ── */
.page-header {
    background: linear-gradient(135deg, #1E3A5F 0%, #2A6496 50%, #1A7A58 100%);
    border-radius: 0 0 var(--radius-xl) var(--radius-xl);
    padding: 26px 32px 22px;
    margin: 0 -24px 24px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: var(--shadow-md);
}

.ph-left {
    display: flex;
    align-items: center;
    gap: 16px;
}

.ph-icon {
    font-size: 38px;
    filter: drop-shadow(0 2px 8px rgba(0,0,0,0.3));
}

.ph-title {
    color: white;
    font-size: 20px;
    font-weight: 800;
    margin: 0 0 3px;
    line-height: 1.2;
}
.ph-sub {
    color: rgba(255,255,255,0.65);
    font-size: 11px;
    font-weight: 500;
    margin: 0;
    letter-spacing: 0.3px;
}

.ph-badges {
    display: flex;
    gap: 8px;
    flex-direction: column;
    align-items: flex-end;
}

.badge {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    padding: 4px 10px;
    border-radius: 16px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 0.3px;
    white-space: nowrap;
}
.badge-green {
    background: rgba(16,185,129,0.2);
    color: #6EE7B7;
    border: 1px solid rgba(16,185,129,0.3);
}
.badge-blue {
    background: rgba(96,165,250,0.2);
    color: #93C5FD;
    border: 1px solid rgba(96,165,250,0.3);
}

/* ════════════════════════════════════
   WELCOME SCREEN
   ════════════════════════════════════ */
.welcome-container {
    text-align: center;
    padding: 40px 20px 20px;
}
.welcome-emoji {
    font-size: 80px;
    display: block;
    margin-bottom: 20px;
    filter: drop-shadow(0 8px 20px rgba(0,0,0,0.12));
    animation: welcomeFloat 3.5s ease-in-out infinite;
}
@keyframes welcomeFloat {
    0%,100% { transform: translateY(0) scale(1); }
    50%      { transform: translateY(-12px) scale(1.03); }
}

.welcome-title {
    color: var(--primary);
    font-size: 28px;
    font-weight: 900;
    margin: 0 0 8px;
}
.welcome-subtitle {
    color: var(--text-sub);
    font-size: 15px;
    margin: 0 0 32px;
    max-width: 520px;
    margin-left: auto;
    margin-right: auto;
    line-height: 1.7;
}

/* ── Feature Chips ── */
.feature-row {
    display: flex;
    justify-content: center;
    gap: 10px;
    flex-wrap: wrap;
    margin-bottom: 36px;
}
.feature-chip {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    background: white;
    border: 1px solid var(--border);
    border-radius: 20px;
    font-size: 12px;
    color: var(--text-sub);
    font-weight: 500;
    box-shadow: var(--shadow-sm);
}

/* ── Example Queries Grid ── */
.examples-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(210px, 1fr));
    gap: 12px;
    max-width: 760px;
    margin: 0 auto;
}
.example-card {
    background: white;
    border: 2px solid var(--border);
    border-radius: var(--radius);
    padding: 16px;
    cursor: pointer;
    transition: all 0.25s;
    text-align: right;
    box-shadow: var(--shadow-sm);
}
.example-card:hover {
    border-color: var(--secondary);
    box-shadow: var(--shadow);
    transform: translateY(-3px);
}
.example-card-icon { font-size: 22px; display: block; margin-bottom: 8px; }
.example-card-label {
    font-size: 11px;
    color: var(--text-muted);
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    margin-bottom: 4px;
    display: block;
}
.example-card-text {
    font-size: 13px;
    color: var(--text);
    font-weight: 500;
    line-height: 1.5;
}

/* ════════════════════════════════════
   CHAT MESSAGES
   ════════════════════════════════════ */
.chat-history {
    display: flex;
    flex-direction: column;
    gap: 20px;
    padding-bottom: 8px;
}

/* ── User Message ── */
.msg-user {
    display: flex;
    justify-content: flex-end;
    align-items: flex-end;
    gap: 10px;
    animation: msgIn 0.3s ease-out;
}
/* ── AI Message ── */
.msg-ai {
    display: flex;
    justify-content: flex-start;
    align-items: flex-end;
    gap: 10px;
    animation: msgIn 0.3s ease-out;
}
@keyframes msgIn {
    from { opacity: 0; transform: translateY(12px); }
    to   { opacity: 1; transform: translateY(0); }
}

/* ── Avatars ── */
.avatar {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 20px;
    flex-shrink: 0;
    box-shadow: var(--shadow);
}
.avatar-user {
    background: linear-gradient(135deg, #1E3A5F, #2E8BC0);
    order: 1;
}
.avatar-ai {
    background: linear-gradient(135deg, #0B5E3D, #0B8457);
    order: -1;
}

/* ── Bubbles ── */
.bubble {
    max-width: 76%;
    padding: 14px 18px;
    font-size: 14px;
    line-height: 1.75;
    color: var(--text);
    box-shadow: var(--shadow);
    position: relative;
    word-break: break-word;
}
.bubble-user {
    background: linear-gradient(145deg, #EBF5FB, #D6EAF8);
    border: 1px solid #AED6F1;
    border-radius: var(--radius) var(--radius-sm) var(--radius) var(--radius);
    order: 0;
}
.bubble-ai {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: var(--radius-sm) var(--radius) var(--radius) var(--radius);
    order: 0;
}

.bubble-footer {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 6px;
    margin-top: 8px;
    font-size: 10px;
    color: var(--text-muted);
}
.bubble-footer-ai { justify-content: flex-start; }

/* ── Bubble inner markdown ── */
.bubble h1,.bubble h2,.bubble h3 { color: var(--primary); }
.bubble h1 { font-size: 17px; }
.bubble h2 { font-size: 15px; }
.bubble h3 { font-size: 13px; }
.bubble p { margin: 0 0 8px; }
.bubble p:last-child { margin-bottom: 0; }
.bubble ul, .bubble ol { padding-right: 18px; margin: 6px 0; }
.bubble li { margin-bottom: 4px; }
.bubble table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
    margin: 10px 0;
    border-radius: var(--radius-sm);
    overflow: hidden;
}
.bubble th {
    background: var(--primary);
    color: white;
    padding: 8px 12px;
    font-weight: 700;
    font-size: 11px;
}
.bubble td {
    padding: 7px 12px;
    border-bottom: 1px solid var(--border);
}
.bubble tr:nth-child(even) td { background: #F7FAFC; }
.bubble code {
    background: #F1F5F9;
    border: 1px solid #E2E8F0;
    border-radius: 4px;
    padding: 1px 5px;
    font-size: 12px;
    font-family: 'Courier New', monospace;
    direction: ltr;
    display: inline-block;
}
.bubble pre {
    background: #1E293B;
    border-radius: var(--radius-sm);
    padding: 12px;
    overflow-x: auto;
    direction: ltr;
}
.bubble pre code {
    background: none;
    border: none;
    color: #E2E8F0;
    font-size: 12px;
}
.bubble blockquote {
    border-right: 4px solid var(--secondary);
    background: #EBF8FF;
    margin: 8px 0;
    padding: 8px 14px;
    border-radius: 0 var(--radius-sm) var(--radius-sm) 0;
    color: var(--text-sub);
    font-style: italic;
}
.bubble strong { color: var(--primary); }
.bubble a { color: var(--secondary); }

/* ════════════════════════════════════
   TOOL CALL INDICATORS
   ════════════════════════════════════ */
.tool-call-card {
    background: linear-gradient(135deg, #FFFBEB, #FEF3C7);
    border: 1px solid #F59E0B;
    border-radius: var(--radius-sm);
    padding: 10px 14px;
    margin: 6px 0;
    font-size: 12px;
}
.tool-call-header {
    display: flex;
    align-items: center;
    gap: 6px;
    color: #92400E;
    font-weight: 700;
    margin-bottom: 4px;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}
.tool-call-name {
    font-size: 12px;
    color: #78350F;
    font-weight: 600;
    font-family: monospace;
    background: rgba(0,0,0,0.06);
    padding: 2px 6px;
    border-radius: 4px;
}

/* ════════════════════════════════════
   THINKING INDICATOR
   ════════════════════════════════════ */
.thinking-card {
    background: linear-gradient(135deg, #FAF5FF, #EDE9FE);
    border: 1px solid #A78BFA;
    border-radius: var(--radius-sm);
    padding: 12px 16px;
    margin: 6px 0;
    display: flex;
    align-items: center;
    gap: 10px;
}
.thinking-text {
    color: #5B21B6;
    font-size: 12px;
    font-weight: 600;
}
.thinking-dots {
    display: inline-flex;
    gap: 5px;
}
.thinking-dots span {
    width: 7px;
    height: 7px;
    background: #7C3AED;
    border-radius: 50%;
    animation: thinkBounce 1.4s infinite ease-in-out;
}
.thinking-dots span:nth-child(2) { animation-delay: 0.16s; }
.thinking-dots span:nth-child(3) { animation-delay: 0.32s; }
@keyframes thinkBounce {
    0%,80%,100% { transform: scale(0.5); opacity: 0.4; }
    40%         { transform: scale(1);   opacity: 1;   }
}

/* ════════════════════════════════════
   INPUT AREA
   ════════════════════════════════════ */
.input-wrapper {
    position: sticky;
    bottom: 0;
    z-index: 100;
    padding: 12px 0 4px;
    background: linear-gradient(to top, var(--bg) 75%, transparent 100%);
}

.input-card {
    background: var(--card);
    border: 2px solid var(--border);
    border-radius: var(--radius-xl);
    padding: 12px 16px 10px;
    box-shadow: var(--shadow-md);
    transition: border-color 0.25s, box-shadow 0.25s;
}
.input-card:focus-within {
    border-color: var(--secondary);
    box-shadow: 0 0 0 4px rgba(46,139,192,0.1), var(--shadow-md);
}

/* ── Streamlit textarea inside input-card ── */
[data-testid="stTextArea"] {
    margin: 0 !important;
}
[data-testid="stTextArea"] > div {
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    border-radius: 0 !important;
}
[data-testid="stTextArea"] textarea {
    font-family: 'Cairo', 'Tajawal', sans-serif !important;
    font-size: 14px !important;
    direction: rtl !important;
    border: none !important;
    box-shadow: none !important;
    background: transparent !important;
    resize: none !important;
    color: var(--text) !important;
    padding: 4px 0 !important;
    min-height: 46px !important;
}
[data-testid="stTextArea"] textarea::placeholder { color: var(--text-muted) !important; }
[data-testid="stTextArea"] textarea:focus { outline: none !important; }

/* ── Input action buttons ── */
.input-actions {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 8px;
}
.input-hint {
    font-size: 10px;
    color: var(--text-muted);
}

/* Send button */
.send-col .stButton > button {
    font-family: 'Cairo', sans-serif !important;
    background: linear-gradient(135deg, #1E3A5F, #2E5B8C) !important;
    color: white !important;
    border: none !important;
    border-radius: var(--radius) !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    padding: 8px 20px !important;
    width: 100% !important;
    transition: all 0.2s !important;
    box-shadow: 0 3px 10px rgba(30,58,95,0.35) !important;
}
.send-col .stButton > button:hover {
    background: linear-gradient(135deg, #2E5B8C, #3A79B8) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 6px 16px rgba(30,58,95,0.4) !important;
}
.send-col .stButton > button:active {
    transform: translateY(0) !important;
}

/* Clear (secondary) button */
.clear-col .stButton > button {
    font-family: 'Cairo', sans-serif !important;
    background: transparent !important;
    color: var(--text-muted) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    padding: 8px 14px !important;
    width: 100% !important;
    transition: all 0.2s !important;
}
.clear-col .stButton > button:hover {
    background: #FEF2F2 !important;
    border-color: #FECACA !important;
    color: #DC2626 !important;
}

/* ── File Upload ── */
[data-testid="stFileUploader"] > div {
    border: 2px dashed var(--border) !important;
    border-radius: var(--radius) !important;
    background: rgba(255,255,255,0.6) !important;
    transition: all 0.2s !important;
}
[data-testid="stFileUploader"] > div:hover {
    border-color: var(--secondary) !important;
    background: #EBF8FF !important;
}

/* ════════════════════════════════════
   ALERT / INFO CARDS
   ════════════════════════════════════ */
.alert {
    padding: 12px 16px;
    border-radius: var(--radius-sm);
    font-size: 13px;
    display: flex;
    align-items: flex-start;
    gap: 10px;
    margin: 8px 0;
}
.alert-icon { font-size: 16px; flex-shrink: 0; margin-top: 1px; }
.alert-info    { background: #EBF8FF; border: 1px solid #BEE3F8; color: #2C5282; }
.alert-warning { background: #FFFBEB; border: 1px solid #FCD34D; color: #78350F; }
.alert-success { background: #F0FFF4; border: 1px solid #9AE6B4; color: #22543D; }
.alert-danger  { background: #FFF5F5; border: 1px solid #FEB2B2; color: #742A2A; }

/* ════════════════════════════════════
   SCROLLBAR
   ════════════════════════════════════ */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E0; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #A0AEC0; }

/* ════════════════════════════════════
   EXPANDER
   ════════════════════════════════════ */
[data-testid="stExpander"] {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    background: white !important;
    box-shadow: var(--shadow-sm) !important;
}
[data-testid="stExpander"] summary {
    font-size: 13px !important;
    font-weight: 600 !important;
    color: var(--text) !important;
}

/* ════════════════════════════════════
   SPINNER
   ════════════════════════════════════ */
.stSpinner > div {
    border-top-color: var(--secondary) !important;
}

/* ════════════════════════════════════
   RESPONSIVE
   ════════════════════════════════════ */
@media (max-width: 768px) {
    .bubble { max-width: 92%; }
    .examples-grid { grid-template-columns: 1fr; }
    .page-header { padding: 18px 20px; }
    .ph-title { font-size: 16px; }
    .ph-badges { display: none; }
}
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# Constants
# ═══════════════════════════════════════════════════════════════

TOOLS_MANIFEST = [
    ("🔬", "بحث PubMed",           "pubmed"),
    ("🧮", "حسابات بصرية",          "calculator"),
    ("📚", "قاعدة المعرفة",         "knowledge_base"),
    ("📄", "توليد التقارير",         "documents"),
    ("📋", "التقييم الوظيفي",        "functional_assessment"),
    ("🔭", "توصية الأجهزة",          "device_recommender"),
    ("📖", "قراءة عربية",            "arabic_reading"),
    ("💭", "فحص نفسي",              "depression_screening"),
    ("📊", "تتبع النتائج",           "outcome_tracker"),
    ("📨", "الإحالة",                "referral"),
    ("🎯", "توصية التقنيات",         "technique_recommender"),
    ("🧠", "التعلم الإدراكي",        "perceptual_learning"),
    ("🏠", "تقييم البيئة",           "environmental_assessment"),
    ("💻", "جلسة عن بعد",           "telerehab"),
    ("🔍", "جلب مقال",              "pubmed_fetch"),
    ("📐", "خطة تأهيل",             "outcome_plan"),
    ("🏥", "تقييم CDSS",             "cdss_evaluate"),
    ("📈", "تقييمات سريرية",          "clinical_assessment"),
    ("⚡", "تدخلات علاجية",           "clinical_intervention"),
]

EXAMPLE_QUERIES = [
    ("👁️", "تدهور البصر المركزي", "AMD",
     "مريضة 72 سنة، AMD رطبة، VA: 6/60، تشكو من صعوبة القراءة. ما برنامج التأهيل المناسب؟"),
    ("🧠", "إصابة دماغية", "Stroke + Hemianopia",
     "مريض 58 سنة، سكتة دماغية قبل 3 أشهر، شقي يميني، يصطدم بالأشياء. ما الخطة؟"),
    ("👶", "تأهيل أطفال", "Pediatric CVI",
     "طفل 5 سنوات، إعاقة بصرية قشرية (CVI) درجة 7/10. ما التدخلات المناسبة؟"),
    ("🔭", "أجهزة مساعدة", "Device Selection",
     "شاب 35 سنة، رتينيتيس بيغمنتوزا، رؤية أنبوبية 5°. ما أفضل جهاز مساعد؟"),
    ("📏", "حسابات تكبير", "Magnification",
     "احسب مستوى التكبير المطلوب للقراءة: VA الحالي 6/60، هدف 1M print size"),
    ("🏠", "تأهيل بيئي", "Environmental",
     "مسن 80 سنة، ضعف بصر ثنائي، تاريخ سقوط مرتين. ما التعديلات البيئية المطلوبة؟"),
]

# ═══════════════════════════════════════════════════════════════
# Session State
# ═══════════════════════════════════════════════════════════════

def init_session():
    if "messages" not in st.session_state:
        st.session_state.messages = []          # {role, content, time, tool_calls}
    if "thinking_budget" not in st.session_state:
        st.session_state.thinking_budget = 8000
    if "use_thinking" not in st.session_state:
        st.session_state.use_thinking = True
    if "pending_query" not in st.session_state:
        st.session_state.pending_query = None

init_session()

# ═══════════════════════════════════════════════════════════════
# Backend — Chat with History
# ═══════════════════════════════════════════════════════════════

def chat_with_history(user_text: str, images: list | None = None) -> dict:
    """
    يرسل رسالة مع الحفاظ على تاريخ المحادثة.
    يُعيد dict: {text, tool_calls, thinking_used}
    """
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""))

    user_text = sanitize_patient_input(user_text)

    # بناء قائمة messages للـ API من تاريخ الجلسة
    api_messages = []
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            api_messages.append({"role": "user", "content": [{"type": "text", "text": msg["content"]}]})
        else:
            api_messages.append({"role": "assistant", "content": [{"type": "text", "text": msg["content"]}]})

    # الرسالة الحالية
    current_content = []
    if images:
        for img in images:
            current_content.append({
                "type": "image",
                "source": {"type": "base64", "media_type": img["media_type"], "data": img["data"]}
            })
    current_content.append({"type": "text", "text": user_text})
    api_messages.append({"role": "user", "content": current_content})

    api_params = {
        "model": "claude-sonnet-4-6",
        "max_tokens": 16384,
        "system": SYSTEM_PROMPT,
        "tools": TOOLS,
        "messages": api_messages,
    }
    if st.session_state.use_thinking:
        api_params["thinking"] = {
            "type": "enabled",
            "budget_tokens": st.session_state.thinking_budget,
        }

    tool_calls_log = []

    # حلقة Tool Use
    while True:
        response = client.messages.create(**api_params)

        if response.stop_reason == "end_turn":
            result_text = extract_text_response(response)
            return {
                "text": validate_medical_output(result_text),
                "tool_calls": tool_calls_log,
                "thinking_used": st.session_state.use_thinking,
            }

        if response.stop_reason == "tool_use":
            api_params["messages"].append({"role": "assistant", "content": response.content})
            tool_results = []
            for block in response.content:
                if hasattr(block, "type") and block.type == "tool_use":
                    result = execute_tool(block.name, block.input)
                    tool_calls_log.append({
                        "name": block.name,
                        "input_preview": str(block.input)[:120],
                    })
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": json.dumps(result, ensure_ascii=False),
                    })
            api_params["messages"].append({"role": "user", "content": tool_results})
        else:
            result_text = extract_text_response(response)
            return {"text": validate_medical_output(result_text), "tool_calls": tool_calls_log, "thinking_used": False}


# ═══════════════════════════════════════════════════════════════
# Rendering Helpers
# ═══════════════════════════════════════════════════════════════

TOOL_NAME_MAP = {t[2]: t[1] for t in TOOLS_MANIFEST}

def tool_display_name(raw_name: str) -> str:
    for key, label in TOOL_NAME_MAP.items():
        if key in raw_name:
            return label
    return raw_name


def render_tool_calls(tool_calls: list):
    if not tool_calls:
        return
    for tc in tool_calls:
        st.markdown(f"""
        <div class="tool-call-card">
            <div class="tool-call-header">⚙️ استخدام أداة</div>
            <span class="tool-call-name">{tool_display_name(tc['name'])}</span>
            <div style="color:#78350F;font-size:10px;margin-top:4px;font-family:monospace;opacity:0.7">
                {tc['input_preview']}…
            </div>
        </div>""", unsafe_allow_html=True)


def render_message(msg: dict):
    role = msg["role"]
    content = msg["content"]
    ts = msg.get("time", "")
    tool_calls = msg.get("tool_calls", [])

    if role == "user":
        st.markdown(f"""
        <div class="msg-user">
            <div class="avatar avatar-user">👤</div>
            <div>
                <div class="bubble bubble-user">{content}</div>
                <div class="bubble-footer">{ts}</div>
            </div>
        </div>""", unsafe_allow_html=True)
    else:
        # Render tool calls first
        if tool_calls:
            st.markdown('<div style="padding-right:48px">', unsafe_allow_html=True)
            render_tool_calls(tool_calls)
            st.markdown('</div>', unsafe_allow_html=True)

        # AI bubble uses st.markdown for rich content
        col_av, col_bub = st.columns([0.06, 0.94])
        with col_av:
            st.markdown('<div class="avatar avatar-ai" style="margin-top:4px">🤖</div>', unsafe_allow_html=True)
        with col_bub:
            st.markdown(
                f'<div class="bubble bubble-ai" style="max-width:100%">',
                unsafe_allow_html=True
            )
            st.markdown(content)
            st.markdown(
                f'<div class="bubble-footer bubble-footer-ai">{ts}</div></div>',
                unsafe_allow_html=True
            )


def render_welcome():
    st.markdown("""
    <div class="welcome-container">
        <span class="welcome-emoji">👁️</span>
        <h2 class="welcome-title">مرحباً بك في مستشار التأهيل البصري</h2>
        <p class="welcome-subtitle">
            نظام ذكاء اصطناعي متخصص يجمع بين المعرفة السريرية العميقة وأحدث بروتوكولات
            التأهيل البصري المدعومة بالأدلة العلمية. اكتب سؤالك أو اختر أحد الأمثلة أدناه.
        </p>
        <div class="feature-row">
            <span class="feature-chip">🧠 تفكير سريري عميق</span>
            <span class="feature-chip">📚 16 أداة متخصصة</span>
            <span class="feature-chip">🔬 PubMed مباشر</span>
            <span class="feature-chip">🌍 عربي + إنجليزي</span>
            <span class="feature-chip">⚡ استجابة فورية</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="examples-grid">', unsafe_allow_html=True)
    cols = st.columns(3)
    for i, (icon, label, tag, query) in enumerate(EXAMPLE_QUERIES):
        with cols[i % 3]:
            if st.button(f"{icon} {label}\n{tag}", key=f"ex_{i}", use_container_width=True):
                st.session_state.pending_query = query
                st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════
# CDSS Tab renderer
# ═══════════════════════════════════════════════════════════════

def render_cdss_tab():
    """عرض تبويب تقييم CDSS الكامل"""
    st.markdown("""
    <div style="padding:16px 0 8px">
        <h3 style="margin:0;color:#1E3A5F;font-family:'Cairo',sans-serif">
            🏥 نظام دعم القرار السريري (CDSS)
        </h3>
        <p style="color:#4A5568;font-size:13px;margin:4px 0 0">
            تقييم شامل مبني على قواعد YAML · حواجز أمان سريرية · مبررات XAI · تتبع النتائج
        </p>
    </div>
    """, unsafe_allow_html=True)

    input_mode = st.radio(
        "نوع الإدخال",
        ["📝 إدخال يدوي", "📋 FHIR Bundle (JSON)"],
        horizontal=True,
        key="cdss_input_mode",
    )

    patient_data = {}

    # ── Manual input ──
    if input_mode == "📝 إدخال يدوي":
        with st.expander("بيانات المريض", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                patient_id = st.text_input("معرف المريض (اختياري)", key="cdss_pid", placeholder="PT-001")
                age = st.number_input("العمر", min_value=1, max_value=120, value=65, key="cdss_age")
                va_logmar = st.number_input(
                    "حدة الإبصار (LogMAR)", min_value=-0.3, max_value=3.0,
                    value=1.0, step=0.1, format="%.1f", key="cdss_va"
                )
                phq9 = st.number_input(
                    "PHQ-9", min_value=0, max_value=27, value=0, key="cdss_phq9"
                )
            with col2:
                icd10_input = st.text_input(
                    "رموز ICD-10 (مفصولة بفاصلة)",
                    key="cdss_icd10",
                    placeholder="H35.30, H35.32",
                )
                patterns = st.multiselect(
                    "نمط فقد الإبصار",
                    ["central_scotoma", "hemianopia", "tunnel_vision",
                     "total_blindness", "peripheral_loss", "general_blur"],
                    key="cdss_patterns",
                )
                goals = st.multiselect(
                    "الأهداف الوظيفية",
                    ["reading", "face_recognition", "mobility", "driving",
                     "computer_use", "tv_watching", "writing", "ADL"],
                    key="cdss_goals",
                )
                setting = st.selectbox(
                    "البيئة", ["clinic", "home", "community"], key="cdss_setting"
                )
            cog_status = st.selectbox(
                "الحالة الإدراكية",
                ["normal", "mild_impairment", "moderate_impairment", "severe_impairment"],
                key="cdss_cog",
            )
            equipment = st.multiselect(
                "المعدات المتوفرة",
                ["MAIA", "MP-3", "NeuroEyeCoach", "NovaVision", "VRT_software"],
                key="cdss_equip",
            )
            language = st.radio("لغة التقرير", ["ar", "en"], horizontal=True, key="cdss_lang")

        icd10_list = [c.strip() for c in icd10_input.split(",") if c.strip()] if icd10_input else []

        patient_data = {
            "patient_id": patient_id if patient_id else None,
            "age": age,
            "active_icd10": icd10_list,
            "vision_patterns": patterns,
            "va_logmar": va_logmar if va_logmar else None,
            "phq9_score": phq9 if phq9 else None,
            "functional_goals": goals,
            "cognitive_status": cog_status,
            "equipment_available": equipment,
            "setting": setting,
            "language": language,
        }

        run_btn = st.button("🔍 تشغيل تقييم CDSS", key="cdss_run_manual", type="primary")

    # ── FHIR input ──
    else:
        fhir_json = st.text_area(
            "الصق FHIR Bundle JSON هنا",
            height=250,
            key="cdss_fhir_json",
            placeholder='{"resourceType": "Bundle", "entry": [...]}',
        )
        patient_id_fhir = st.text_input("معرف المريض (اختياري)", key="cdss_fhir_pid", placeholder="PT-001")
        lang_fhir = st.radio("لغة التقرير", ["ar", "en"], horizontal=True, key="cdss_fhir_lang")
        run_btn = st.button("🔍 تشغيل تقييم CDSS", key="cdss_run_fhir", type="primary")

    # ── Run evaluation ──
    if run_btn:
        with st.spinner("يعالج البيانات..."):
            try:
                if input_mode == "📝 إدخال يدوي":
                    params = {
                        "input_type": "manual",
                        "patient_data": patient_data,
                        "patient_id": patient_data.get("patient_id"),
                        "language": patient_data.get("language", "ar"),
                    }
                else:
                    if not fhir_json or not fhir_json.strip():
                        st.error("الرجاء إدخال FHIR Bundle JSON")
                        return
                    fhir_bundle = json.loads(fhir_json)
                    params = {
                        "input_type": "fhir",
                        "fhir_bundle": fhir_bundle,
                        "patient_id": patient_id_fhir if patient_id_fhir else None,
                        "language": lang_fhir,
                    }

                result = run_cdss_evaluation(params)
                _render_cdss_result(result)

            except json.JSONDecodeError as e:
                st.error(f"خطأ في تحليل JSON: {e}")
            except Exception as e:
                st.error(f"خطأ في التقييم: {e}")


def _render_cdss_result(result: dict):
    """عرض نتائج تقييم CDSS"""
    if "error" in result:
        st.error(f"⛔ {result['error']}")
        return

    # ── Guardrail alerts ──
    errors = result.get("errors", [])
    warnings = result.get("warnings", [])

    if errors:
        for err in errors:
            msg = err.get("message_ar", str(err)) if isinstance(err, dict) else str(err)
            st.error(f"🔴 **خطأ سريري:** {msg}")

    if warnings:
        for warn in warnings:
            msg = warn.get("message_ar", str(warn)) if isinstance(warn, dict) else str(warn)
            st.warning(f"🟡 {msg}")

    # ── Summary ──
    recs = result.get("recommendations", [])

    col1, col2, col3 = st.columns(3)
    col1.metric("القواعد المُقيَّمة", result.get("total_rules_evaluated", "—"))
    col2.metric("التوصيات المطابقة", result.get("total_matched", len(recs)))
    col3.metric("التحقق", "✅ صالح" if result.get("is_valid", True) else "⛔ أخطاء")

    # ── Clinical report (Markdown) ──
    report = result.get("clinical_report", "") or result.get("report", "")
    if report:
        st.markdown("---")
        st.markdown(report)
    elif recs:
        st.markdown("---")
        st.subheader(f"التوصيات ({len(recs)} تقنية)")
        for i, rec in enumerate(recs, 1):
            with st.expander(f"{i}. {rec.get('technique_ar', rec.get('technique', ''))} — أولوية {rec.get('priority', '')}"):
                c1, c2 = st.columns(2)
                c1.write(f"**مستوى الدليل:** {rec.get('evidence_level', '')}")
                c2.write(f"**نقاط الملاءمة:** {rec.get('suitability_score', '')}")
                st.write(f"**الإجراء:** {rec.get('action', '')}")
                if rec.get("justification"):
                    st.info(f"**المبرر:** {rec['justification']}")
                if rec.get("outcome_note"):
                    st.warning(rec["outcome_note"])
                if rec.get("experimental"):
                    st.caption("⚠️ تجريبي — لم يُثبت بعد")

    # ── Audit Trail ──
    audit = result.get("audit_trail", {})
    if audit:
        with st.expander("🔍 مسار التدقيق (Audit Trail)", expanded=False):
            st.json(audit)


# ═══════════════════════════════════════════════════════════════
# Assessment Tab renderer
# ═══════════════════════════════════════════════════════════════

def render_assessment_tab():
    """عرض تبويب التقييمات السريرية الرقمية"""
    from assessments import run_assessment

    st.markdown("""
    <div style="padding:16px 0 8px">
        <h3 style="margin:0;color:#1E3A5F;font-family:'Cairo',sans-serif">📈 التقييمات السريرية الرقمية (Digital Biomarkers)</h3>
        <p style="color:#4A5568;font-size:13px;margin:4px 0 0">
            BCEA · MNREAD · Visual Search · Contrast Sensitivity
        </p>
    </div>
    """, unsafe_allow_html=True)

    assess_type = st.selectbox(
        "نوع التقييم",
        ["fixation", "reading", "visual_search", "contrast"],
        format_func=lambda x: {
            "fixation": "👁️ ثبات التثبيت (BCEA)",
            "reading": "📖 سرعة القراءة (MNREAD)",
            "visual_search": "🔍 المسح البصري (Cancellation Test)",
            "contrast": "🎨 حساسية التباين (Pelli-Robson)",
        }.get(x, x),
        key="assess_type",
    )

    if assess_type == "fixation":
        st.subheader("👁️ تحليل ثبات التثبيت (BCEA)")
        st.info("أدخل إحداثيات تتبع العين (X, Y) لجلستين لمقارنة التقدم.")
        col1, col2 = st.columns(2)
        with col1:
            s1x = st.text_input("Session 1 — X coords (مفصولة بفاصلة)", "0.5, 0.7, -0.2, 1.2, 0.9, 0.3, -0.1, 0.8", key="fix_s1x")
            s1y = st.text_input("Session 1 — Y coords", "0.1, -0.5, 0.8, 1.1, -0.2, 0.4, -0.3, 0.6", key="fix_s1y")
        with col2:
            s2x = st.text_input("Session 2 — X coords", "0.1, 0.2, 0.0, -0.1, 0.1, 0.05, -0.05, 0.15", key="fix_s2x")
            s2y = st.text_input("Session 2 — Y coords", "0.0, 0.1, -0.1, 0.0, 0.2, -0.05, 0.1, -0.1", key="fix_s2y")

        if st.button("تحليل التثبيت", key="run_fixation", type="primary"):
            try:
                params = {
                    "assessment_type": "fixation", "action": "evaluate_progress",
                    "session1_x": [float(x) for x in s1x.split(",")],
                    "session1_y": [float(x) for x in s1y.split(",")],
                    "session2_x": [float(x) for x in s2x.split(",")],
                    "session2_y": [float(x) for x in s2y.split(",")],
                }
                result = run_assessment(params)
                c1, c2, c3 = st.columns(3)
                c1.metric("BCEA قبل", f"{result['bcea_before']} deg²")
                c2.metric("BCEA بعد", f"{result['bcea_after']} deg²")
                c3.metric("التحسن", f"{result['improvement_pct']}%")
                st.success(f"**الحالة:** {result['status_ar']} — **الإجراء:** {result['action_ar']}")
                st.json(result)
            except Exception as e:
                st.error(f"خطأ: {e}")

    elif assess_type == "reading":
        st.subheader("📖 اختبار سرعة القراءة (Digital MNREAD)")
        st.info("أدخل قراءات MNREAD: حجم الخط (LogMAR)، زمن القراءة (ثانية)، أخطاء الكلمات.")
        num = st.number_input("عدد القراءات", 3, 10, 5, key="mnread_n")
        readings = []
        for i in range(int(num)):
            cols = st.columns(3)
            size = cols[0].number_input(f"حجم {i+1} (LogMAR)", 0.0, 1.5, 1.0 - i * 0.2, 0.1, key=f"mn_s{i}")
            time_s = cols[1].number_input(f"زمن {i+1} (ث)", 1.0, 120.0, 5.0 + i * 3, 0.5, key=f"mn_t{i}")
            errs = cols[2].number_input(f"أخطاء {i+1}", 0, 10, min(i, 5), key=f"mn_e{i}")
            readings.append({"print_size_logmar": size, "reading_time_seconds": time_s, "word_errors": int(errs)})

        if st.button("تحليل القراءة", key="run_mnread", type="primary"):
            result = run_assessment({"assessment_type": "reading", "readings": readings})
            c1, c2, c3 = st.columns(3)
            c1.metric("MRS", f"{result['mrs_wpm']} WPM")
            c2.metric("CPS", f"{result['cps_logmar']} LogMAR")
            c3.metric("RA", f"{result['reading_acuity_logmar']} LogMAR")
            st.write(f"**التصنيف:** {result['speed_classification']['label_ar']}")
            if result.get("recommendations"):
                for rec in result["recommendations"]:
                    st.warning(f"**توصية:** {rec['action_ar']}")
            with st.expander("التفاصيل"):
                st.json(result)

    elif assess_type == "contrast":
        st.subheader("🎨 اختبار حساسية التباين")
        method = st.radio("الطريقة", ["pelli_robson", "staircase"], horizontal=True, key="cs_method")

        if method == "pelli_robson":
            st.info("أدخل عدد الحروف الصحيحة (0–3) لكل مستوى تباين.")
            levels = [0.0, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.20, 1.35]
            responses = []
            cols = st.columns(5)
            for i, lvl in enumerate(levels):
                c = cols[i % 5]
                correct = c.number_input(f"LogCS {lvl}", 0, 3, 3 if i < 5 else 2, key=f"pr_{i}")
                responses.append({"log_cs_level": lvl, "letters_correct": int(correct)})

            if st.button("تحليل التباين", key="run_cs", type="primary"):
                result = run_assessment({"assessment_type": "contrast", "method": "pelli_robson", "responses": responses})
                c1, c2 = st.columns(2)
                c1.metric("LogCS", result["threshold_logcs"])
                c2.metric("التصنيف", result["classification"]["label_ar"])
                if result.get("recommendations"):
                    for rec in result["recommendations"]:
                        st.warning(f"{rec['action_ar']}")

    elif assess_type == "visual_search":
        st.subheader("🔍 اختبار المسح البصري")
        st.info("محاكاة اختبار شطب رقمي لتقييم الإهمال البصري.")
        diff = st.slider("مستوى الصعوبة", 1, 5, 2, key="vs_diff")
        targets = st.slider("عدد الأهداف", 10, 40, 20, key="vs_targets")

        if st.button("توليد اختبار", key="run_vs", type="primary"):
            result = run_assessment({"assessment_type": "visual_search", "action": "generate_trial", "difficulty": diff, "target_count": targets})
            st.success(f"تم توليد {result['total_targets']} هدف + {result['total_distractors']} مشتت بصعوبة {diff}")
            st.json(result)


# ═══════════════════════════════════════════════════════════════
# Intervention Tab renderer
# ═══════════════════════════════════════════════════════════════

def render_intervention_tab():
    """عرض تبويب التدخلات العلاجية"""
    from interventions import run_intervention

    st.markdown("""
    <div style="padding:16px 0 8px">
        <h3 style="margin:0;color:#1E3A5F;font-family:'Cairo',sans-serif">⚡ التدخلات العلاجية الرقمية (Digital Therapeutics)</h3>
        <p style="color:#4A5568;font-size:13px;margin:4px 0 0">
            Scanning Training · Perceptual Learning · AR Augmentation · Device Routing
        </p>
    </div>
    """, unsafe_allow_html=True)

    int_type = st.selectbox(
        "نوع التدخل",
        ["scanning", "perceptual_learning", "device_routing", "visual_augmentation"],
        format_func=lambda x: {
            "scanning": "🎯 تدريب المسح البصري (Hemianopia)",
            "perceptual_learning": "🧠 التعلم الإدراكي (Gabor Patch)",
            "device_routing": "🔭 التوجيه الذكي للمعدات",
            "visual_augmentation": "👓 التعزيز البصري (AR Demo)",
        }.get(x, x),
        key="int_type",
    )

    if int_type == "scanning":
        st.subheader("🎯 محاكاة جلسة تدريب المسح البصري")
        col1, col2 = st.columns(2)
        blind_side = col1.selectbox("الجانب الأعمى", ["right", "left"], key="scan_side")
        num_trials = col2.slider("عدد المحاولات", 10, 50, 20, key="scan_n")

        if st.button("تشغيل المحاكاة", key="run_scan", type="primary"):
            result = run_intervention({
                "intervention_type": "scanning", "action": "simulate_session",
                "blind_side": blind_side, "num_trials": num_trials,
            })
            s = result["session_summary"]
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("المحاولات", s["total_trials"])
            c2.metric("الدقة", f"{s['accuracy_pct']}%")
            c3.metric("أعلى صعوبة", s["max_difficulty_reached"])
            c4.metric("الانعكاسات", s["total_reversals"])

            st.write(f"**عتبة الصعوبة:** {s['threshold_difficulty']}")

            with st.expander("تفاصيل المحاولات"):
                for t in result["trials"]:
                    icon = "✅" if t["correct"] else "❌"
                    st.write(f"{icon} Trial {t['trial']}: RT={t['rt_ms']}ms | Diff→{t['new_difficulty']} | {t['feedback']}")

    elif int_type == "perceptual_learning":
        st.subheader("🧠 محاكاة جلسة التعلم الإدراكي")
        col1, col2 = st.columns(2)
        sc = col1.slider("تباين البداية", 0.1, 1.0, 1.0, 0.05, key="pl_sc")
        num_t = col2.slider("عدد المحاولات", 20, 100, 50, key="pl_n")

        if st.button("تشغيل المحاكاة", key="run_pl", type="primary"):
            result = run_intervention({
                "intervention_type": "perceptual_learning", "action": "simulate_session",
                "starting_contrast": sc, "num_trials": num_t,
            })
            s = result["session_summary"]
            c1, c2, c3 = st.columns(3)
            c1.metric("المحاولات", s["total_trials"])
            c2.metric("الدقة", f"{s['accuracy_pct']}%")
            c3.metric("التباين النهائي", f"{s['ending_contrast']:.3f}")

            threshold = s.get("threshold_estimate", {})
            if threshold.get("estimated"):
                st.success(f"**عتبة التباين:** {threshold['threshold_pct']}% (LogCS: {threshold['threshold_logcs']})")

            with st.expander("منحنى التباين"):
                contrasts = [t["contrast"] for t in result["trials"]]
                st.line_chart(contrasts)

    elif int_type == "device_routing":
        st.subheader("🔭 التوجيه الذكي للمعدات المساعدة")
        col1, col2 = st.columns(2)
        va = col1.number_input("VA (LogMAR)", 0.0, 3.0, 1.0, 0.1, key="dr_va")
        vf = col2.number_input("مجال الرؤية (درجات)", 0.0, 180.0, 60.0, 5.0, key="dr_vf")
        cog = st.checkbox("تدهور إدراكي", key="dr_cog")
        goals = st.multiselect("الأهداف", ["reading", "mobility", "face_recognition", "computer_use"], key="dr_goals")
        budget = st.number_input("الميزانية ($)", 0, 10000, 5000, 500, key="dr_budget")

        if st.button("توصية الجهاز", key="run_dr", type="primary"):
            result = run_intervention({
                "intervention_type": "device_routing",
                "va_logmar": va, "visual_field_degrees": vf,
                "has_cognitive_decline": cog, "functional_goals": goals,
                "budget_usd": budget,
            })
            for w in result.get("guardrail_warnings", []):
                st.warning(f"⚠️ {w.get('message_ar', w)}")

            dev = result.get("primary_device")
            if dev:
                st.success(f"**الجهاز الموصى:** {dev['name_ar']} ({dev['name']}) — ${dev['price_usd']}")
                st.write(f"**الفئة:** {dev['category']} | **النمط:** {dev['modality']}")
                st.info(result.get("justification_ar", ""))
                if result.get("alternatives"):
                    st.write("**البدائل:**")
                    for alt in result["alternatives"]:
                        st.write(f"  - {alt['name_ar']} — ${alt['price_usd']}")
            else:
                st.error("لم يُعثر على جهاز مناسب.")

    elif int_type == "visual_augmentation":
        st.subheader("👓 عرض توضيحي للتعزيز البصري")
        st.info("محاكاة معالجة صورة لأنماط مختلفة من ضعف البصر.")

        if st.button("تشغيل العرض التوضيحي", key="run_va", type="primary"):
            result = run_intervention({"intervention_type": "visual_augmentation", "action": "demo"})
            modes = result.get("demo_results", {})
            for mode, data in modes.items():
                if mode == "environment_analysis":
                    st.write(f"**تحليل البيئة:** إضاءة تقديرية {data.get('estimated_lux', 'N/A')} لوكس | "
                             f"وهج: {data.get('glare_risk', 'N/A')} | تباين: {data.get('contrast_quality', 'N/A')}")
                    for rec in data.get("recommendations", []):
                        st.warning(f"  {rec.get('issue_ar', '')}: {rec.get('action_ar', '')}")
                else:
                    st.write(f"**{mode}:** تم المعالجة بنجاح ✅ ({data.get('shape', '')})")


# ═══════════════════════════════════════════════════════════════
# Sidebar
# ═══════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div class="sb-header">
        <span class="sb-logo">🏥</span>
        <h2 class="sb-title">مستشار التأهيل البصري</h2>
        <p class="sb-subtitle">Vision Rehab AI Consultant</p>
        <div class="sb-model-badge">🤖 Claude Sonnet 4.6</div>
    </div>
    <div class="sb-body">
    """, unsafe_allow_html=True)

    # ── Stats ──
    n_msgs = len(st.session_state.messages)
    n_user = sum(1 for m in st.session_state.messages if m["role"] == "user")
    st.markdown(f"""
    <div class="sb-section-label">إحصائيات الجلسة</div>
    <div class="sb-stats">
        <div class="sb-stat"><span class="sb-stat-num">{n_user}</span><span class="sb-stat-lbl">استفسار</span></div>
        <div class="sb-stat"><span class="sb-stat-num">17</span><span class="sb-stat-lbl">أداة نشطة</span></div>
        <div class="sb-stat"><span class="sb-stat-num">34</span><span class="sb-stat-lbl">مدخلة معرفية</span></div>
        <div class="sb-stat"><span class="sb-stat-num">26</span><span class="sb-stat-lbl">جهاز مساعد</span></div>
    </div>
    <div class="sb-divider"></div>
    """, unsafe_allow_html=True)

    # ── Tools ──
    st.markdown('<div class="sb-section-label">الأدوات المتاحة</div>', unsafe_allow_html=True)
    for icon, name, _ in TOOLS_MANIFEST:
        st.markdown(f"""
        <div class="tool-chip">
            <span class="tool-chip-icon">{icon}</span>
            <span class="tool-chip-name">{name}</span>
            <span class="tool-chip-badge">نشط</span>
        </div>""", unsafe_allow_html=True)

    st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

    # ── Settings ──
    st.markdown('<div class="sb-section-label">الإعدادات</div>', unsafe_allow_html=True)
    st.session_state.use_thinking = st.toggle(
        "🧠 التفكير العميق (Extended Thinking)",
        value=st.session_state.use_thinking,
    )
    if st.session_state.use_thinking:
        st.session_state.thinking_budget = st.select_slider(
            "حد رموز التفكير",
            options=[2000, 4000, 8000, 12000, 16000],
            value=st.session_state.thinking_budget,
        )

    st.markdown('<div class="sb-divider"></div>', unsafe_allow_html=True)

    # ── Clear ──
    if st.button("🗑️ مسح المحادثة", key="clear_chat"):
        st.session_state.messages = []
        st.session_state.pending_query = None
        st.rerun()

    # ── Disclaimer ──
    st.markdown("""
    <div style="margin-top:14px;padding:10px;background:rgba(255,255,255,0.04);border-radius:8px;border:1px solid rgba(255,255,255,0.07)">
        <p style="color:rgba(255,255,255,0.35);font-size:9px;line-height:1.6;margin:0">
            ⚠️ هذا النظام أداة مساعدة للمتخصصين ولا يُغني عن التقييم السريري المباشر.
            جميع التوصيات يجب مراجعتها من متخصص مؤهل.
        </p>
    </div>
    </div>
    """, unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# Main Content
# ═══════════════════════════════════════════════════════════════

# ── Page Header ──
st.markdown("""
<div class="page-header">
    <div class="ph-left">
        <span class="ph-icon">👁️</span>
        <div>
            <h1 class="ph-title">مستشار التأهيل البصري الذكي</h1>
            <p class="ph-sub">Vision Rehabilitation AI Consultant · Claude Sonnet 4.6</p>
        </div>
    </div>
    <div class="ph-badges">
        <span class="badge badge-green">● متصل</span>
        <span class="badge badge-blue">🔬 19 أداة</span>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ──
tab_chat, tab_cdss, tab_assess, tab_intervene = st.tabs([
    "💬 المستشار الذكي", "🏥 تقييم CDSS", "📈 التقييمات السريرية", "⚡ التدخلات العلاجية"
])

with tab_cdss:
    render_cdss_tab()

with tab_assess:
    render_assessment_tab()

with tab_intervene:
    render_intervention_tab()

with tab_chat:
    # ── Chat History ──
    chat_area = st.container()
    with chat_area:
        if not st.session_state.messages:
            render_welcome()
        else:
            for msg in st.session_state.messages:
                render_message(msg)

    # ── Input Area ──
    st.markdown('<div class="input-wrapper"><div class="input-card">', unsafe_allow_html=True)

    uploaded_file = None
    show_upload = st.checkbox("📎 إرفاق صورة طبية", value=False, key="show_upload")
    if show_upload:
        uploaded_file = st.file_uploader(
            "ارفع صورة طبية (OCT, VF, Fundus, إلخ)",
            type=["png", "jpg", "jpeg", "webp"],
            key="file_upload",
            label_visibility="collapsed",
        )

    user_input = st.text_area(
        label="رسالتك",
        placeholder="اكتب سؤالك السريري هنا… (مثال: مريض 65 سنة، AMD، VA: 6/120، يريد العودة للقراءة)",
        key="user_input",
        height=80,
        label_visibility="collapsed",
    )

    col_send, col_clear, col_hint = st.columns([2, 1, 4])
    with col_send:
        st.markdown('<div class="send-col">', unsafe_allow_html=True)
        send_btn = st.button("إرسال ↗", key="send", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col_clear:
        st.markdown('<div class="clear-col">', unsafe_allow_html=True)
        clear_btn = st.button("مسح", key="clear_input", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with col_hint:
        st.markdown(
            '<div style="padding:10px 0;font-size:10px;color:#718096">Ctrl+Enter للإرسال السريع</div>',
            unsafe_allow_html=True
        )

    st.markdown('</div></div>', unsafe_allow_html=True)

    # ── Handle Send ──

    # Handle pending example query
    if st.session_state.pending_query:
        query = st.session_state.pending_query
        st.session_state.pending_query = None
        user_input = query
        send_btn = True

    if clear_btn:
        st.rerun()

    if send_btn and user_input and user_input.strip():
        query = user_input.strip()
        now = datetime.now().strftime("%H:%M")

        # Process image if uploaded
        images = None
        if uploaded_file:
            img_bytes = uploaded_file.read()
            img_b64 = base64.standard_b64encode(img_bytes).decode("utf-8")
            ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
            media_type_map = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp"}
            images = [{"media_type": media_type_map.get(ext, "image/jpeg"), "data": img_b64}]

        # Add user message to history
        st.session_state.messages.append({
            "role": "user",
            "content": query,
            "time": now,
            "tool_calls": [],
        })

        # Show spinner while processing
        with st.spinner(""):
            st.markdown("""
            <div class="thinking-card" style="margin:8px 0">
                <div class="thinking-dots">
                    <span></span><span></span><span></span>
                </div>
                <span class="thinking-text">الذكاء الاصطناعي يحلل استفسارك…</span>
            </div>
            """, unsafe_allow_html=True)

            try:
                result = chat_with_history(query, images)
                ai_text = result["text"]
                tool_calls = result["tool_calls"]

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": ai_text,
                    "time": datetime.now().strftime("%H:%M"),
                    "tool_calls": tool_calls,
                })
            except Exception as e:
                err_msg = f"حدث خطأ: {str(e)}"
                st.session_state.messages.append({
                    "role": "assistant",
                    "content": f"⚠️ {err_msg}",
                    "time": datetime.now().strftime("%H:%M"),
                    "tool_calls": [],
                })

        st.rerun()
