# Meetora — AI Meeting Analyzer (Frontend)

An intelligent web-based application that analyzes meeting recordings, audio files, and transcripts to extract actionable insights and improve meeting productivity.

Built with **React 19**, **Vite 8**, **TypeScript**, and **Tailwind CSS v4**.

---

## 🌟 Key Features

- **Executive Meeting Dashboard**: Real-time meeting oversight, sentiment dynamic metrics, task progress, and upcoming agendas.
- **Diarized Transcripts**: Speaker identification with timestamps and multi-speaker voice clustering.
- **Multilingual Transcription & Translation**: Indian vernacular support (Hindi, Tamil, Telugu, Kannada, Bengali, Marathi) and English with instant bilingual toggle views.
- **AI-Powered Meeting Summaries**: Hierarchical executive summaries, bulleted key discussion points, and immediate next steps.
- **Automated Action Items & Confidence Scores**: 4-class sentence classification with amber "Needs Review" badges and Human-in-the-Loop (HITL) corrections.
- **Ask Your Meetings (RAG AI Chatbot)**: Semantic Q&A grounded strictly in meeting transcripts with clickable timestamp citations (`[12:18 Sarah Kim]`). Available in 3 formats:
  - Meeting Detail tab
  - Full-screen Workspace AI Chatbot
  - Persistent Floating Chatbot Widget on all screens
- **Meeting Chapters & Effectiveness Score**: Structured topic chapters timeline and an 88/100 meeting effectiveness gauge across 4 operational pillars.
- **Calendar & Reminders**: Google Calendar 1-click sync and Celery Beat deadline alert notifications.
- **Multi-Format Export**: 1-click export to PDF, Word (.docx), Markdown (.md), and automated follow-up email drafts with Nodemailer dispatch.
- **Team Workspace Hub**: Collaborator management, voice biometric profiles, speaking-time distribution analytics, and Nodemailer invitations.
- **Admin Control Center**: User administration, cross-meeting oversight, Model Evaluation dashboard (Precision, Recall, F1, WER, Confusion Matrix), and Model Registry versioning.
- **Interactive Notification Center**: Dropdown menu with unread badges, instant meeting jump links, and notification preference controls.
- **Security & Profile**: Profile photo upload, password reset, and RFC 6238 TOTP Two-Factor Authentication (2FA) with scannable QR Code.
- **Themes**: Instant Light and Dark mode switching with high-contrast accessibility.

---

## 🛠️ Tech Stack

- **Framework**: React 19 + TypeScript
- **Build Tool**: Vite 8
- **Styling**: Tailwind CSS v4 (`@tailwindcss/vite`)
- **Icons**: Custom SVG Icon system
- **API Client**: Axios with JWT interceptors, automatic token refresh, and resilient offline fallbacks

---

## 🚀 Getting Started

### 1. Install Dependencies
```bash
npm install
```

### 2. Start Development Server
```bash
npm run dev
```
The application will be live at `http://localhost:5173` (or port configured by Vite).

### 3. Production Build
```bash
npm run build
```

---

## 📁 Project Structure

```text
├── public/                 # Static assets & favicons
├── src/
│   ├── components/         # Reusable charts & analytics components
│   ├── api.ts              # Centralized API service & mock fallbacks
│   ├── App.tsx             # Primary React component & dashboard router
│   ├── main.tsx            # React root entrypoint
│   └── index.css           # Tailwind CSS v4 styling & theme classes
├── index.html              # HTML shell
├── vite.config.ts          # Vite configuration
├── tsconfig.json           # TypeScript configuration
└── package.json            # Project dependencies & scripts
```

---

## 📄 License
MIT License.

