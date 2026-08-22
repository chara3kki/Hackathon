
const state = {
  experience: null,
  goal: null,
  availability: null
};

const steps = [...document.querySelectorAll(".quiz-step")];
const progress = document.getElementById("quizProgress");
const result = document.getElementById("quizResult");

function showStep(n) {
  steps.forEach(step => step.classList.toggle("active", Number(step.dataset.step) === n));
  result.classList.add("hidden");
  progress.textContent = `Question ${n} of 3`;
}

document.querySelectorAll("[data-experience]").forEach(btn => {
  btn.addEventListener("click", () => {
    state.experience = btn.dataset.experience;
    showStep(2);
  });
});

document.querySelectorAll("[data-goal]").forEach(btn => {
  btn.addEventListener("click", () => {
    state.goal = btn.dataset.goal;
    showStep(3);
  });
});

document.querySelectorAll("[data-availability]").forEach(btn => {
  btn.addEventListener("click", () => {
    state.availability = btn.dataset.availability;
    finishQuiz();
  });
});

function finishQuiz() {
  steps.forEach(step => step.classList.remove("active"));
  progress.textContent = "Your result";
  result.classList.remove("hidden");

  const title = document.getElementById("resultTitle");
  const text = document.getElementById("resultText");
  const notes = document.getElementById("resultNotes");
  const link = document.getElementById("resultLink");

  if (state.experience === "never") {
    title.textContent = "Start with Learn to Row";
    text.textContent = "You do not need previous rowing experience or a fitness base. Learn to Row is designed to teach complete beginners from the first stroke.";
    if (state.availability === "weekend") {
      notes.textContent = "Weekend term-based adult programs are likely to be the first listings to check. Use the current course page for exact dates, availability and price.";
    } else if (state.availability === "early") {
      notes.textContent = "Red Shed also runs early-morning intensive formats at times during the year. Check the current listing to see what is open now.";
    } else {
      notes.textContent = "Check the current course listings and choose the format that best fits your week.";
    }
    link.href = "https://redshed.org.au/learn-to-row/";
    link.textContent = "See Learn to Row options";
  } else if (state.experience === "old") {
    title.textContent = "You have two sensible pathways";
    text.textContent = "If you want a complete refresher, Learn to Row is still available to you. If your old skills feel comfortable, Red Shed's continuing pathway may be a better fit.";
    notes.textContent = "This is one of the recurring questions in Red Shed enquiries, so the goal is to help returning rowers self-place before needing to email.";
    link.href = "https://redshed.org.au/continuing-to-row/";
    link.textContent = "See continuing options";
  } else {
    title.textContent = "Explore Continue to Row";
    text.textContent = "If you already row, Learn to Row is probably not your first stop. Development, Squad, casual sessions and passes are part of Red Shed's continuing pathway.";
    notes.textContent = "Entry requirements vary, so check the current Red Shed continuing-to-row information before booking.";
    link.href = "https://redshed.org.au/continuing-to-row/";
    link.textContent = "See Continue to Row";
  }
}

document.getElementById("restartQuiz").addEventListener("click", () => {
  state.experience = state.goal = state.availability = null;
  showStep(1);
});

const knowledge = [
  {
    keys: ["never", "beginner", "experience", "first time"],
    answer: "Learn to Row is built for complete beginners. No rowing experience is needed, and the skills are taught from the beginning. If you want, use “Find My Rowing Path” above and then check the current Learn to Row course dates."
  },
  {
    keys: ["fit", "fitness", "unfit", "exercise"],
    answer: "You do not need to be fit before starting adult Learn to Row. Red Shed says the program builds fitness gradually while you learn."
  },
  {
    keys: ["swim", "swimming", "water"],
    answer: "Red Shed asks every rower to be able to swim 50 metres and tread water. If that is a concern, it is one of the cases where you should contact Red Shed before booking."
  },
  {
    keys: ["old", "age", "too old", "50", "60"],
    answer: "There is no ‘too old’ message in Red Shed’s adult Learn to Row guidance. Their adult programs regularly include rowers in their 50s, 60s and beyond."
  },
  {
    keys: ["years ago", "return", "rowed before", "refresher", "forgot"],
    answer: "If you rowed years ago, you can start fresh with Learn to Row or consider Continue to Row if you still have a comfortable base. The pathway tool above can point you in the right direction."
  },
  {
    keys: ["when", "time", "date", "start", "weekend", "morning", "schedule"],
    answer: "Red Shed runs different Learn to Row formats through the year. Adult options can include weekend term programs and early-morning intensives. Exact dates, times, availability and price are kept on the current booking listing."
  },
  {
    keys: ["wear", "bring", "clothes", "clothing"],
    answer: "Wear fitted, comfortable activewear and avoid loose clothing that can catch in moving parts. Bring socks, a water bottle, sunscreen, a hat and a warm layer in cooler weather. Red Shed provides the boats, oars, safety gear and coaching."
  },
  {
    keys: ["miss", "late", "started", "join after"],
    answer: "Red Shed says programs can remain open after week one at the full program fee, but whether joining late is sensible depends on how far the course has progressed."
  },
  {
    keys: ["price", "cost", "fee", "how much"],
    answer: "Learn to Row is a fixed-length program with a single program fee rather than an ongoing membership. The current booking listing is the right place to check the exact price because it varies by program."
  }
];

function answerQuestion(q) {
  const text = q.toLowerCase();
  let best = null;
  let score = 0;

  for (const item of knowledge) {
    const s = item.keys.reduce((n, k) => n + (text.includes(k) ? 1 : 0), 0);
    if (s > score) { score = s; best = item; }
  }

  if (best) return best.answer;

  return "I don’t have a verified answer for that in this prototype knowledge base. For the production version, the AI guide should answer only from approved Red Shed information and route anything uncertain to staff rather than inventing an answer.";
}

function appendMessage(role, text) {
  const wrap = document.createElement("div");
  wrap.className = `message ${role}`;
  wrap.innerHTML = role === "bot"
    ? `<strong>Rowing Guide</strong><p>${escapeHtml(text)}</p>`
    : `<p>${escapeHtml(text)}</p>`;
  const messages = document.getElementById("chatMessages");
  messages.appendChild(wrap);
  messages.scrollTop = messages.scrollHeight;
}

function escapeHtml(str) {
  return str.replace(/[&<>"']/g, ch => ({
    "&":"&amp;", "<":"&lt;", ">":"&gt;", '"':"&quot;", "'":"&#039;"
  }[ch]));
}

function ask(q) {
  if (!q.trim()) return;
  appendMessage("user", q);
  setTimeout(() => appendMessage("bot", answerQuestion(q)), 180);
}

document.getElementById("chatForm").addEventListener("submit", e => {
  e.preventDefault();
  const input = document.getElementById("chatInput");
  const q = input.value;
  input.value = "";
  ask(q);
});

document.querySelectorAll("[data-prompt]").forEach(btn => {
  btn.addEventListener("click", () => ask(btn.dataset.prompt));
});
