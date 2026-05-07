const ui = {
  menuBtn: document.getElementById("menuBtn"),
  closeDrawerBtn: document.getElementById("closeDrawerBtn"),
  drawer: document.getElementById("drawer"),
  drawerBackdrop: document.getElementById("drawerBackdrop"),
  navLinks: document.querySelectorAll(".nav-link"),
  pages: document.querySelectorAll(".page"),

  sourceBadge: document.getElementById("sourceBadge"),
  sourceStatus: document.getElementById("sourceStatus"),
  fileInput: document.getElementById("fileInput"),
  youtubeInput: document.getElementById("youtubeInput"),
  loadYoutubeBtn: document.getElementById("loadYoutubeBtn"),
  loadSampleBtn: document.getElementById("loadSampleBtn"),

  readingInput: document.getElementById("readingInput"),
  analyzeReadingBtn: document.getElementById("analyzeReadingBtn"),
  readingStats: document.getElementById("readingStats"),
  readingArea: document.getElementById("readingArea"),
  sentenceList: document.getElementById("sentenceList"),
  readingQuestionList: document.getElementById("readingQuestionList"),
  generateReadingQuestionsBtn: document.getElementById("generateReadingQuestionsBtn"),

  listeningInput: document.getElementById("listeningInput"),
  generateListeningTasksBtn: document.getElementById("generateListeningTasksBtn"),
  listeningTaskList: document.getElementById("listeningTaskList"),
  playTtsBtn: document.getElementById("playTtsBtn"),
  stopTtsBtn: document.getElementById("stopTtsBtn"),

  writingPrompt: document.getElementById("writingPrompt"),
  writingInput: document.getElementById("writingInput"),
  generateWritingPromptBtn: document.getElementById("generateWritingPromptBtn"),
  evaluateWritingBtn: document.getElementById("evaluateWritingBtn"),
  writingFeedbackList: document.getElementById("writingFeedbackList"),

  wordMenu: document.getElementById("wordMenu"),
  closeWordMenuBtn: document.getElementById("closeWordMenuBtn"),
  menuWord: document.getElementById("menuWord"),
  menuPos: document.getElementById("menuPos"),
  menuCefr: document.getElementById("menuCefr"),
  menuMeaning: document.getElementById("menuMeaning"),
  menuHint: document.getElementById("menuHint"),
};

const sampleText = `Climate adaptation policies increasingly require interdisciplinary research. Many institutions now integrate environmental data with social indicators to improve decision quality. If policy-makers review both qualitative and quantitative evidence, they usually design more resilient systems.`;

const state = {
  sourceText: "",
  sourceLabel: "Henüz yüklenmedi",
  lastParagraphs: [],
};

const localDictionary = {
  adaptation: "uyum sağlama",
  interdisciplinary: "disiplinler arası",
  indicators: "göstergeler",
  resilient: "dayanıklı",
  evidence: "kanıt",
  policy: "politika",
  institution: "kurum",
  integrate: "entegre etmek",
  quantitative: "nicel",
  qualitative: "nitel",
};

const posLexicon = {
  determiner: new Set(["the", "a", "an", "this", "that", "these", "those", "my", "your", "our", "their", "its", "each", "every", "some", "any", "few", "many", "much", "several"]),
  conjunction: new Set(["and", "but", "or", "because", "although", "if", "when", "while", "since", "unless", "however", "therefore"]),
  preposition: new Set(["in", "on", "at", "by", "for", "with", "about", "from", "to", "into", "through", "over", "under", "between", "within"]),
  auxiliary: new Set(["is", "are", "was", "were", "be", "been", "being", "do", "does", "did", "have", "has", "had", "can", "could", "may", "might", "must", "will", "would", "should"]),
};

bindEvents();
loadSample();

function bindEvents() {
  ui.menuBtn.addEventListener("click", openDrawer);
  ui.closeDrawerBtn.addEventListener("click", closeDrawer);
  ui.drawerBackdrop.addEventListener("click", closeDrawer);

  ui.navLinks.forEach((link) => {
    link.addEventListener("click", () => {
      setPage(link.dataset.page);
      closeDrawer();
    });
  });

  ui.fileInput.addEventListener("change", onFileUpload);
  ui.loadYoutubeBtn.addEventListener("click", onYoutubeLoad);
  ui.loadSampleBtn.addEventListener("click", loadSample);

  ui.analyzeReadingBtn.addEventListener("click", analyzeReading);
  ui.generateReadingQuestionsBtn.addEventListener("click", () => {
    renderReadingQuestions(generateReadingQuestions(state.lastParagraphs));
  });

  ui.generateListeningTasksBtn.addEventListener("click", () => {
    renderListeningTasks(generateListeningTasks(ui.listeningInput.value));
  });
  ui.playTtsBtn.addEventListener("click", playTts);
  ui.stopTtsBtn.addEventListener("click", () => window.speechSynthesis?.cancel());

  ui.generateWritingPromptBtn.addEventListener("click", () => {
    ui.writingPrompt.textContent = generateWritingPromptFromText(state.sourceText || ui.readingInput.value);
  });
  ui.evaluateWritingBtn.addEventListener("click", evaluateWriting);

  ui.closeWordMenuBtn.addEventListener("click", closeWordMenu);
  document.addEventListener("click", (e) => {
    if (!ui.wordMenu.contains(e.target)) closeWordMenu();
  });
  document.addEventListener("contextmenu", onWordContextMenu);
  ui.readingArea.addEventListener("click", onWordTap);
}

function openDrawer() {
  ui.drawer.classList.add("open");
  ui.drawerBackdrop.classList.add("show");
}

function closeDrawer() {
  ui.drawer.classList.remove("open");
  ui.drawerBackdrop.classList.remove("show");
}

function setPage(pageId) {
  ui.pages.forEach((p) => p.classList.toggle("active", p.id === pageId));
  ui.navLinks.forEach((n) => n.classList.toggle("active", n.dataset.page === pageId));
}

function setSourceStatus(label, detail = "") {
  state.sourceLabel = label;
  ui.sourceBadge.textContent = `Kaynak: ${label}`;
  ui.sourceStatus.textContent = detail ? `Durum: ${detail}` : `Durum: ${label}`;
}

async function onFileUpload(event) {
  const [file] = event.target.files || [];
  if (!file) return;

  if (file.name.toLowerCase().endsWith(".txt")) {
    const text = await file.text();
    applySourceContent(text, `TXT - ${file.name}`, "TXT başarıyla işlendi.");
    return;
  }

  if (file.name.toLowerCase().endsWith(".pdf")) {
    setSourceStatus("PDF", "PDF okunuyor...");
    const text = await extractTextFromPdf(file);
    if (!text) {
      setSourceStatus("PDF", "PDF okunamadı. Metni manuel yapıştırabilirsiniz.");
      return;
    }
    applySourceContent(text, `PDF - ${file.name}`, "PDF başarıyla işlendi.");
  }
}

async function onYoutubeLoad() {
  const url = ui.youtubeInput.value.trim();
  if (!url) return;

  setSourceStatus("YouTube", "YouTube içeriği çekiliyor...");
  const text = await extractTextFromYoutube(url);
  if (!text) {
    setSourceStatus("YouTube", "YouTube transcript alınamadı. Link doğruysa transcripti manuel yapıştırın.");
    return;
  }

  applySourceContent(text, "YouTube", "YouTube transcript içeriği işlendi.");
}

function loadSample() {
  applySourceContent(sampleText, "Örnek içerik", "Örnek içerik yüklendi.");
}

function applySourceContent(text, label, detail) {
  state.sourceText = normalizeText(text);
  ui.readingInput.value = state.sourceText;
  ui.listeningInput.value = state.sourceText;
  ui.writingPrompt.textContent = generateWritingPromptFromText(state.sourceText);

  analyzeReading();
  renderListeningTasks(generateListeningTasks(state.sourceText));
  setSourceStatus(label, detail);
}

function normalizeText(text) {
  return (text || "").replace(/\r/g, "").replace(/\n{3,}/g, "\n\n").trim();
}

async function extractTextFromPdf(file) {
  try {
    const mod = await import("https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.2.67/pdf.min.mjs");
    const pdfjs = mod.default || mod;
    if (pdfjs?.GlobalWorkerOptions) {
      pdfjs.GlobalWorkerOptions.workerSrc = "https://cdnjs.cloudflare.com/ajax/libs/pdf.js/4.2.67/pdf.worker.min.mjs";
    }

    const arrayBuffer = await file.arrayBuffer();
    const doc = await pdfjs.getDocument({ data: arrayBuffer }).promise;
    let full = "";

    for (let page = 1; page <= doc.numPages; page += 1) {
      const p = await doc.getPage(page);
      const content = await p.getTextContent();
      full += `${content.items.map((i) => i.str).join(" ")}\n\n`;
    }

    return normalizeText(full);
  } catch {
    return "";
  }
}

async function extractTextFromYoutube(url) {
  const id = parseYoutubeId(url);
  if (!id) return "";

  const endpoints = [
    `https://youtubetranscript.com/?server_vid2=${id}`,
    `https://www.youtube.com/oembed?url=${encodeURIComponent(url)}&format=json`,
  ];

  for (const endpoint of endpoints) {
    try {
      const res = await fetch(endpoint);
      if (!res.ok) continue;

      const type = res.headers.get("content-type") || "";
      if (type.includes("application/json")) {
        const data = await res.json();
        if (data?.title) {
          return `${data.title}. This transcript is unavailable automatically. Please paste transcript for better listening tasks.`;
        }
      } else {
        const raw = await res.text();
        const cleaned = raw.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
        if (cleaned.length > 80) return cleaned;
      }
    } catch {
      // try next endpoint
    }
  }

  return "";
}

function parseYoutubeId(url) {
  try {
    const u = new URL(url);
    if (u.hostname.includes("youtu.be")) return u.pathname.slice(1);
    return u.searchParams.get("v") || "";
  } catch {
    return "";
  }
}

function analyzeReading() {
  const text = normalizeText(ui.readingInput.value);
  if (!text) {
    ui.readingArea.innerHTML = '<p class="muted">Analiz için metin girin.</p>';
    ui.sentenceList.innerHTML = "";
    ui.readingQuestionList.innerHTML = "";
    ui.readingStats.textContent = "Henüz analiz yapılmadı.";
    state.lastParagraphs = [];
    return;
  }

  const paragraphs = splitParagraphs(text);
  const sentences = splitSentences(text);
  state.lastParagraphs = paragraphs;

  const analyses = renderReadingArea(paragraphs);
  renderSentenceAnalysis(sentences);
  renderReadingStats(text, paragraphs, analyses);
  renderReadingQuestions(generateReadingQuestions(paragraphs));
}

function splitParagraphs(text) {
  return text.split(/\n\s*\n/).map((p) => p.replace(/\s+/g, " ").trim()).filter(Boolean);
}

function splitSentences(text) {
  return text.replace(/\s+/g, " ").match(/[^.!?]+[.!?]?/g)?.map((s) => s.trim()).filter(Boolean) || [];
}

function renderReadingArea(paragraphs) {
  ui.readingArea.innerHTML = "";
  const analyses = [];

  paragraphs.forEach((paragraph, pIndex) => {
    const p = document.createElement("p");

    (paragraph.match(/[A-Za-z']+|[^A-Za-z']+/g) || []).forEach((chunk) => {
      if (/^[A-Za-z']+$/.test(chunk)) {
        const info = analyzeWord(chunk, pIndex);
        analyses.push(info);

        const span = document.createElement("span");
        span.className = "word-token";
        span.textContent = chunk;
        span.dataset.payload = JSON.stringify(info);
        span.dataset.tag = `${info.pos} | ${info.cefr}`;
        p.appendChild(span);
      } else {
        p.appendChild(document.createTextNode(chunk));
      }
    });

    ui.readingArea.appendChild(p);
  });

  return analyses;
}

function analyzeWord(word, pIndex) {
  const lower = word.toLowerCase();
  const pos = detectPos(lower);
  return {
    word,
    pos,
    cefr: detectCefr(lower, pos),
    meaning: localDictionary[lower] || "Sözlükte yok; bağlamdan çıkarım yap.",
    hint: grammarHint(pos, pIndex),
  };
}

function detectPos(word) {
  if (posLexicon.determiner.has(word)) return "Determiner";
  if (posLexicon.conjunction.has(word)) return "Conjunction";
  if (posLexicon.preposition.has(word)) return "Preposition";
  if (posLexicon.auxiliary.has(word)) return "Auxiliary";
  if (/ly$/.test(word)) return "Adverb";
  if (/ing$|ed$/.test(word)) return "Verb form";
  if (/tion$|ment$|ity$|ness$/.test(word)) return "Noun";
  if (/ous$|ive$|al$|ful$/.test(word)) return "Adjective";
  return "Likely Noun/Verb";
}

function detectCefr(word, pos) {
  if (word.length <= 3) return "A1";
  if (word.length <= 5) return "A2";
  if (/tion$|sion$|ology$|graphy$/.test(word)) return "C1";
  if (word.length >= 14) return "C2";
  if (pos === "Determiner" || pos === "Auxiliary") return "A2";
  if (word.length >= 10) return "B2";
  return "B1";
}

function grammarHint(pos, pIndex) {
  if (pos === "Determiner") return "Article + noun uyumu writing accuracy için önemli.";
  if (pos === "Conjunction") return "Conjunction kullanımı coherence puanını yükseltir.";
  if (pos === "Preposition") return "Preposition collocation IELTS'te kritik.";
  if (pos === "Auxiliary") return "Zaman/kip yapısını taşıyan yardımcı fiil.";
  return `Paragraf ${pIndex + 1} içindeki bağlamı incele.`;
}

function renderSentenceAnalysis(sentences) {
  ui.sentenceList.innerHTML = "";
  sentences.slice(0, 8).forEach((s, i) => {
    const tokens = s.toLowerCase().match(/[a-z']+/g) || [];
    const type = s.endsWith("?") ? "Soru" : s.endsWith("!") ? "Ünlem" : "Bildirme";
    const complex = tokens.some((t) => ["because", "although", "if", "when", "while", "unless"].includes(t));

    const li = document.createElement("li");
    li.textContent = `${i + 1}. ${type} | ${complex ? "Complex" : "Simple/Compound"}`;
    ui.sentenceList.appendChild(li);
  });
}

function renderReadingStats(text, paragraphs, analyses) {
  const words = (text.match(/[A-Za-z']+/g) || []).length;
  const avg = paragraphs.length ? (words / paragraphs.length).toFixed(1) : "0";

  const dist = analyses.reduce((acc, a) => {
    acc[a.cefr] = (acc[a.cefr] || 0) + 1;
    return acc;
  }, {});
  const cefr = ["A1", "A2", "B1", "B2", "C1", "C2"].filter((k) => dist[k]).map((k) => `${k}:${dist[k]}`).join(" | ");

  ui.readingStats.textContent = `${words} kelime | ${paragraphs.length} paragraf | ort ${avg} | CEFR: ${cefr || "-"}`;
}

function generateReadingQuestions(paragraphs) {
  if (!paragraphs.length) return [{ type: "Info", prompt: "Önce kaynak yükleyin.", answer: "-" }];

  const questions = [];
  const heads = paragraphs.map((p, i) => {
    const kw = topKeywords(p, 2);
    return `${kw[0] || "Main"} focus in paragraph ${i + 1}`;
  });

  paragraphs.slice(0, 4).forEach((p, i) => {
    const answerHeading = heads[i];
    const headingOptions = shuffle([answerHeading, ...heads.filter((h) => h !== answerHeading)]).slice(0, 4);

    questions.push({
      type: "Matching Headings",
      prompt: `P${i + 1} için başlık seçin: ${headingOptions.map((o, idx) => `${String.fromCharCode(65 + idx)}) ${o}`).join(" | ")}`,
      answer: `${String.fromCharCode(65 + headingOptions.indexOf(answerHeading))}) ${answerHeading}`,
    });

    const key = topKeywords(p, 1)[0] || "the topic";
    const mcAnswer = `The paragraph explains how ${key} affects outcomes.`;
    const mcOpts = shuffle([
      mcAnswer,
      "The paragraph only gives unrelated historical facts.",
      "The paragraph says study strategies never work.",
      "The paragraph is about entertainment industry news.",
    ]);

    questions.push({
      type: "Multiple Choice",
      prompt: `P${i + 1} ana fikir: ${mcOpts.map((o, idx) => `${String.fromCharCode(65 + idx)}) ${o}`).join(" | ")}`,
      answer: `${String.fromCharCode(65 + mcOpts.indexOf(mcAnswer))}) ${mcAnswer}`,
    });
  });

  questions.push({
    type: "True/False/Not Given",
    prompt: "The text provides exact statistical evidence for every claim.",
    answer: "Not Given",
  });

  return questions;
}

function renderReadingQuestions(questions) {
  ui.readingQuestionList.innerHTML = "";
  questions.forEach((q, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${i + 1}. ${q.type}:</strong> ${q.prompt}<br><span class="muted">Answer: ${q.answer}</span>`;
    ui.readingQuestionList.appendChild(li);
  });
}

function topKeywords(text, limit = 3) {
  const stop = new Set(["the", "a", "an", "and", "or", "but", "of", "to", "in", "on", "for", "with", "is", "are", "was", "were", "be", "been", "it", "this", "that", "if", "when", "while", "as", "by", "from"]);
  const freq = new Map();

  (text.toLowerCase().match(/[a-z']+/g) || []).filter((t) => !stop.has(t) && t.length > 3).forEach((t) => {
    freq.set(t, (freq.get(t) || 0) + 1);
  });

  return [...freq.entries()].sort((a, b) => b[1] - a[1]).slice(0, limit).map(([t]) => t);
}

function generateListeningTasks(transcriptRaw) {
  const transcript = normalizeText(transcriptRaw);
  if (!transcript) return [{ type: "Info", prompt: "Transcript yok.", answer: "-" }];

  const words = transcript.match(/[A-Za-z']+/g) || [];
  const key = topKeywords(transcript, 2)[0] || "topic";
  const gap = topKeywords(transcript, 2)[1] || words[Math.min(6, words.length - 1)] || "information";
  const firstSentence = transcript.split(/[.!?]/)[0] || transcript;
  const gapPrompt = firstSentence.replace(new RegExp(`\\b${escapeRegExp(gap)}\\b`, "i"), "_____ ");

  const mcAnswer = `The speaker explains core points about ${key}.`;
  const opts = shuffle([
    mcAnswer,
    "The speaker is giving sports commentary.",
    "The speaker rejects all planning methods.",
    "The speaker discusses unrelated movie reviews.",
  ]);

  return [
    { type: "Gap Fill", prompt: `Complete: ${gapPrompt}`, answer: gap },
    { type: "Multiple Choice", prompt: `Main purpose: ${opts.map((o, i) => `${String.fromCharCode(65 + i)}) ${o}`).join(" | ")}`, answer: `${String.fromCharCode(65 + opts.indexOf(mcAnswer))}) ${mcAnswer}` },
    { type: "Note Completion", prompt: `Write 2 notes about ${key}.`, answer: "Open-ended" },
  ];
}

function renderListeningTasks(tasks) {
  ui.listeningTaskList.innerHTML = "";
  tasks.forEach((t, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<strong>${i + 1}. ${t.type}:</strong> ${t.prompt}<br><span class="muted">Answer: ${t.answer}</span>`;
    ui.listeningTaskList.appendChild(li);
  });
}

function playTts() {
  const text = normalizeText(ui.listeningInput.value);
  if (!text || !window.speechSynthesis) return;
  window.speechSynthesis.cancel();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = "en-US";
  utterance.rate = 0.95;
  window.speechSynthesis.speak(utterance);
}

function generateWritingPromptFromText(source) {
  const text = normalizeText(source);
  const key = topKeywords(text, 1)[0] || "education";
  return `Task 2: Some people believe that public investment in ${key} should be prioritized, while others think individual responsibility is more important. Discuss both views and give your opinion.`;
}

function evaluateWriting() {
  const text = normalizeText(ui.writingInput.value);
  ui.writingFeedbackList.innerHTML = "";

  if (!text) {
    pushWritingFeedback("Info", "Önce writing cevabı girin.", "-");
    return;
  }

  const words = text.match(/[A-Za-z']+/g) || [];
  const sentences = splitSentences(text);
  const unique = new Set(words.map((w) => w.toLowerCase()));
  const diversity = words.length ? (unique.size / words.length) * 100 : 0;
  const connectors = ["however", "therefore", "moreover", "although", "because", "while", "in contrast", "for example"];
  const connCount = connectors.filter((c) => new RegExp(`\\b${escapeRegExp(c)}\\b`, "i").test(text)).length;
  const longSentences = sentences.filter((s) => (s.match(/[A-Za-z']+/g) || []).length > 30).length;

  const tr = scoreTaskResponse(words.length);
  const cc = scoreCoherence(connCount, sentences.length);
  const lr = scoreLexical(diversity);
  const gr = scoreGrammar(longSentences, sentences.length);
  const overall = ((tr + cc + lr + gr) / 4).toFixed(1);

  pushWritingFeedback("Task Response", `${words.length} kelime`, `Band ${tr.toFixed(1)}`);
  pushWritingFeedback("Coherence & Cohesion", `${connCount} connector`, `Band ${cc.toFixed(1)}`);
  pushWritingFeedback("Lexical Resource", `%${diversity.toFixed(1)} diversity`, `Band ${lr.toFixed(1)}`);
  pushWritingFeedback("Grammar Range & Accuracy", `${longSentences}/${sentences.length} uzun cümle`, `Band ${gr.toFixed(1)}`);
  pushWritingFeedback("Overall", "Rubric ortalaması", `Band ${overall}`);
}

function scoreTaskResponse(wordCount) {
  if (wordCount >= 280) return 7.5;
  if (wordCount >= 250) return 7.0;
  if (wordCount >= 220) return 6.5;
  if (wordCount >= 180) return 6.0;
  return 5.5;
}

function scoreCoherence(connectors, sentenceCount) {
  if (connectors >= 4 && sentenceCount >= 6) return 7.5;
  if (connectors >= 3) return 7.0;
  if (connectors >= 2) return 6.5;
  if (connectors >= 1) return 6.0;
  return 5.5;
}

function scoreLexical(diversity) {
  if (diversity >= 55) return 7.5;
  if (diversity >= 48) return 7.0;
  if (diversity >= 42) return 6.5;
  if (diversity >= 36) return 6.0;
  return 5.5;
}

function scoreGrammar(longSentences, totalSentences) {
  if (totalSentences < 4) return 5.5;
  const ratio = longSentences / totalSentences;
  if (ratio <= 0.25) return 7.0;
  if (ratio <= 0.4) return 6.5;
  if (ratio <= 0.55) return 6.0;
  return 5.5;
}

function pushWritingFeedback(type, detail, score) {
  const li = document.createElement("li");
  li.innerHTML = `<strong>${type}:</strong> ${detail}<br><span class="muted">${score}</span>`;
  ui.writingFeedbackList.appendChild(li);
}

function onWordContextMenu(event) {
  const token = event.target.closest(".word-token");
  if (!token) return;

  event.preventDefault();
  const data = parsePayload(token.dataset.payload);
  openWordMenu(data, event.clientX, event.clientY, token);
}

function onWordTap(event) {
  const token = event.target.closest(".word-token");
  if (!token) return;

  const data = parsePayload(token.dataset.payload);
  const rect = token.getBoundingClientRect();
  openWordMenu(data, rect.left, rect.bottom + 8, token);
}

function parsePayload(payload) {
  try {
    return JSON.parse(payload);
  } catch {
    return { word: "", pos: "Unknown", cefr: "B1", meaning: "", hint: "" };
  }
}

function openWordMenu(data, x, y, token) {
  document.querySelectorAll(".word-token.active").forEach((t) => t.classList.remove("active"));
  token.classList.add("active");

  ui.menuWord.textContent = data.word;
  ui.menuPos.textContent = data.pos;
  ui.menuCefr.textContent = `CEFR: ${data.cefr}`;
  ui.menuMeaning.textContent = data.meaning;
  ui.menuHint.textContent = data.hint;

  const pad = 10;
  const left = Math.max(pad, Math.min(x + 8, window.innerWidth - 340));
  const top = Math.max(pad, Math.min(y + 8, window.innerHeight - 220));
  ui.wordMenu.style.left = `${left}px`;
  ui.wordMenu.style.top = `${top}px`;
  ui.wordMenu.classList.remove("hidden");
}

function closeWordMenu() {
  ui.wordMenu.classList.add("hidden");
  document.querySelectorAll(".word-token.active").forEach((t) => t.classList.remove("active"));
}

function shuffle(arr) {
  const copy = [...arr];
  for (let i = copy.length - 1; i > 0; i -= 1) {
    const j = Math.floor(Math.random() * (i + 1));
    [copy[i], copy[j]] = [copy[j], copy[i]];
  }
  return copy;
}

function escapeRegExp(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}
