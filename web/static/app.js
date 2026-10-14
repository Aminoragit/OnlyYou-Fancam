/**
 * AutoFancam Local Studio — Apple Inspired UX Engine v3.2
 */

let currentJobId = null;
let currentJobData = null;
let selectedPersonId = null;
let pollTimer = null;
let animFrameId = null;

// DOM Elements
const omniInput = document.getElementById("omniInput");
const btnStartJob = document.getElementById("btnStartJob");
const btnUploadTrigger = document.getElementById("btnUploadTrigger");
const fileUploadInput = document.getElementById("fileUploadInput");
const dropZone = document.getElementById("dropZone");
const btnRunDemo = document.getElementById("btnRunDemo");

const systemStatusText = document.getElementById("systemStatusText");
const statusDot = document.querySelector(".status-dot");

const activityPanel = document.getElementById("activityPanel");
const activityLabel = document.getElementById("activityLabel");
const activityPercent = document.getElementById("activityPercent");
const activityFill = document.getElementById("activityFill");

const workspaceSection = document.getElementById("workspaceSection");
const emptyGuideSection = document.getElementById("emptyGuideSection");
const sourceVideo = document.getElementById("sourceVideo");
const hudPerson = document.getElementById("hudPerson");
const hudRatio = document.getElementById("hudRatio");

const playBtn = document.getElementById("playBtn");
const playIcon = document.getElementById("playIcon");
const pauseIcon = document.getElementById("pauseIcon");
const muteBtn = document.getElementById("muteBtn");
const seekBar = document.getElementById("seekBar");
const curTimeText = document.getElementById("curTimeText");
const durTimeText = document.getElementById("durTimeText");

const membersGrid = document.getElementById("membersGrid");
const performersCountPill = document.getElementById("performersCountPill");
const exportList = document.getElementById("exportList");
const exportsCountPill = document.getElementById("exportsCountPill");

// 1. Drag & Drop Universal Handling
['dragenter', 'dragover'].forEach(eventName => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.querySelector('.omnibar-container').classList.add('drag-active');
  }, false);
});

['dragleave', 'drop'].forEach(eventName => {
  dropZone.addEventListener(eventName, (e) => {
    e.preventDefault();
    e.stopPropagation();
    dropZone.querySelector('.omnibar-container').classList.remove('drag-active');
  }, false);
});

dropZone.addEventListener('drop', (e) => {
  const dt = e.dataTransfer;
  const files = dt.files;
  if (files && files.length > 0) {
    handleFileUpload(files[0]);
  }
});

btnUploadTrigger.addEventListener('click', () => fileUploadInput.click());
fileUploadInput.addEventListener('change', (e) => {
  if (e.target.files && e.target.files.length > 0) {
    handleFileUpload(e.target.files[0]);
  }
});

// 2. Demo Trigger
btnRunDemo.addEventListener('click', async () => {
  setSystemProcessing(true, "데모 댄스 무대 영상 분석 착수 중...");
  try {
    const res = await fetch("/api/demo/start", { method: "POST" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "데모 시작 실패");
    startJobMonitoring(data.job_id);
  } catch (err) {
    setSystemProcessing(false, "데모 실행 실패");
    alert("오류: " + err.message);
  }
});

// 3. Omnibar Submit Handling
btnStartJob.addEventListener('click', () => submitOmniInput());
omniInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') {
    submitOmniInput();
  }
});

async function submitOmniInput() {
  const val = omniInput.value.trim().replace(/^["']|["']$/g, '');
  if (!val) {
    omniInput.focus();
    return;
  }

  const isYoutube = /(youtube\.com|youtu\.be)/i.test(val);
  setSystemProcessing(true, isYoutube ? "YouTube 영상 다운로드 준비 중..." : "영상 분석 시작 중...");

  try {
    if (isYoutube) {
      const res = await fetch("/api/jobs/start-youtube", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: val })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "시작 실패");
      startJobMonitoring(data.job_id);
    } else {
      const res = await fetch("/api/jobs/start-path", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ file_path: val })
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "시작 실패");
      startJobMonitoring(data.job_id);
    }
  } catch (err) {
    setSystemProcessing(false, "오류 발생");
    alert("오류: " + err.message);
  }
}

async function handleFileUpload(file) {
  if (!file) return;
  const formData = new FormData();
  formData.append("file", file);

  setSystemProcessing(true, `영상 업로드 중: ${file.name}...`);

  try {
    const res = await fetch("/api/jobs/upload", {
      method: "POST",
      body: formData
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "업로드 실패");
    startJobMonitoring(data.job_id);
  } catch (err) {
    setSystemProcessing(false, "업로드 실패");
    alert("업로드 오류: " + err.message);
  }
}

// 4. Status & Activity Management
function setSystemProcessing(isProcessing, statusMsg) {
  if (isProcessing) {
    statusDot.classList.add("active");
    systemStatusText.textContent = "작업 진행 중";
    activityPanel.style.display = "block";
    activityLabel.textContent = statusMsg;
  } else {
    statusDot.classList.remove("active");
    systemStatusText.textContent = statusMsg || "준비됨";
  }
}

function startJobMonitoring(jobId) {
  currentJobId = jobId;
  localStorage.setItem("autofancam_last_job", jobId);
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(pollJobStatus, 700);
  pollJobStatus();
}

async function pollJobStatus() {
  if (!currentJobId) return;

  try {
    const res = await fetch(`/api/jobs/${currentJobId}/status`);
    if (!res.ok) return;
    const job = await res.json();
    currentJobData = job;

    let overallPct = Math.max(job.fast_lane_percent || 0, job.export_percent || 0);
    activityFill.style.width = `${overallPct}%`;
    activityPercent.textContent = `${overallPct}%`;

    let cleanMsg = job.progress_msg || "처리 중...";
    cleanMsg = cleanMsg.replace(/^Fast Lane:\s*/i, '').replace(/^Export Lane:\s*/i, '');
    activityLabel.textContent = cleanMsg;

    // Reveal Workspace & Hide Guide
    if (job.preview_state === "PREVIEW_READY" || job.preview_state === "CAMERA_PATH_BUILDING" || job.export_state === "EXPORTING" || job.export_state === "ALL_EXPORTED") {
      document.body.classList.add("studio-active");
      workspaceSection.style.display = "grid";
      emptyGuideSection.style.display = "none";

      const srcUrl = `/api/jobs/${currentJobId}/source-video`;
      if (!sourceVideo.src || !sourceVideo.src.includes(currentJobId)) {
        sourceVideo.src = srcUrl;
        sourceVideo.load();
      }

      if (job.identities && job.identities.length > 0) {
        performersCountPill.textContent = `${job.identities.length}명 감지됨`;
        renderPerformers(job.identities);
        if (!selectedPersonId) {
          selectPerformer(job.identities[0].person_id);
        }
      }
    }

    if (job.export_files && job.export_files.length > 0) {
      renderExports(job.export_files);
    }

    if (job.export_state === "ALL_EXPORTED") {
      clearInterval(pollTimer);
      pollTimer = null;
      setSystemProcessing(false, "직캠 생성 완료");
      activityPercent.textContent = "100%";
      activityFill.style.width = "100%";
      setTimeout(() => {
        activityPanel.style.display = "none";
      }, 3000);
    }
  } catch (err) {
    console.error("Poll error:", err);
  }
}

// 5. Performers & Exports Rendering
function renderPerformers(identities) {
  if (!identities || identities.length === 0) return;
  membersGrid.innerHTML = "";

  identities.forEach((m) => {
    const card = document.createElement("div");
    card.className = `performer-card ${selectedPersonId === m.person_id ? "active" : ""}`;
    card.onclick = () => selectPerformer(m.person_id);

    card.innerHTML = `
      <img class="performer-thumb" src="${m.poster_url}" alt="${m.person_id}" onerror="this.src='/static/default_poster.png'">
      <div class="performer-id">${m.person_id}</div>
      <div class="performer-sec">${m.total_tracked_sec}s</div>
    `;
    membersGrid.appendChild(card);
  });
}

function selectPerformer(personId) {
  selectedPersonId = personId;
  hudPerson.textContent = personId;

  document.querySelectorAll(".performer-card").forEach((card) => {
    const isThis = card.querySelector(".performer-id")?.textContent === personId;
    card.classList.toggle("active", isThis);
  });

  updateVirtualFancam();
}

function renderExports(exports) {
  const readyList = exports.filter(e => e.state === "completed");
  exportsCountPill.textContent = `${readyList.length}개 완료`;

  exportList.innerHTML = "";
  readyList.forEach((exp) => {
    const row = document.createElement("div");
    row.className = "export-row";
    row.innerHTML = `
      <div class="export-file-meta">
        <div class="file-icon">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polygon points="5 3 19 12 5 21 5 3"></polygon>
          </svg>
        </div>
        <div>
          <div class="file-name">${exp.person_id}.mp4</div>
          <div class="file-details">9:16 Full HD &bull; H.264 Faststart</div>
        </div>
      </div>
      <a href="${exp.download_url}" download class="download-pill-btn">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
          <polyline points="7 10 12 15 17 10"></polyline>
          <line x1="12" y1="15" x2="12" y2="3"></line>
        </svg>
        <span>다운로드</span>
      </a>
    `;
    exportList.appendChild(row);
  });
}

// 6. 9:16 Virtual Fancam Viewport Engine (Continuous $C^1$ Hermite)
function updateVirtualFancam() {
  if (!currentJobData || !selectedPersonId || !currentJobData.camera_paths) return;
  const path = currentJobData.camera_paths[selectedPersonId];
  if (!path || path.length === 0) return;

  const curSec = sourceVideo.currentTime;
  const curMs = curSec * 1000;

  const roi = getInterpolatedRoi(path, curMs);
  applyViewportTransform(roi);
}

function getInterpolatedRoi(path, t_ms) {
  if (t_ms <= path[0].t_ms) return path[0];
  if (t_ms >= path[path.length - 1].t_ms) return path[path.length - 1];

  let low = 0, high = path.length - 1;
  while (low <= high) {
    const mid = Math.floor((low + high) / 2);
    if (path[mid].t_ms <= t_ms) low = mid + 1;
    else high = mid - 1;
  }
  const p0 = path[Math.max(0, high)];
  const p1 = path[Math.min(path.length - 1, low)];

  if (p0 === p1 || p1.t_ms === p0.t_ms) {
    return p0;
  }

  const alpha = (t_ms - p0.t_ms) / (p1.t_ms - p0.t_ms);
  const smoothAlpha = alpha * alpha * (3.0 - 2.0 * alpha);

  const cx = (1.0 - smoothAlpha) * p0.cx + smoothAlpha * p1.cx;
  const cy = (1.0 - smoothAlpha) * p0.cy + smoothAlpha * p1.cy;
  const w = (1.0 - smoothAlpha) * p0.w + smoothAlpha * p1.w;
  const h = (1.0 - smoothAlpha) * p0.h + smoothAlpha * p1.h;

  return { cx, cy, w, h };
}

function applyViewportTransform(roi) {
  const origW = (currentJobData.source_info && currentJobData.source_info.width) || sourceVideo.videoWidth || 1920;
  const origH = (currentJobData.source_info && currentJobData.source_info.height) || sourceVideo.videoHeight || 1080;
  const viewW = 360;
  const viewH = 640;

  const targetH = roi.h * origH;
  const targetW = targetH * (9 / 16);
  const targetScale = viewH / targetH;
  const cropX1 = (roi.cx * origW) - (targetW / 2);
  const cropY1 = (roi.cy * origH) - (targetH / 2);

  const transX = -cropX1 * targetScale;
  const transY = -cropY1 * targetScale;

  sourceVideo.style.width = `${origW}px`;
  sourceVideo.style.height = `${origH}px`;
  sourceVideo.style.transform = `translate3d(${transX}px, ${transY}px, 0px) scale(${targetScale})`;
}

// 7. Playback & Scrubber Loop
function fancamLoop() {
  if (!sourceVideo.paused && !sourceVideo.ended) {
    updateVirtualFancam();
    updateSeekBar();
  }
  animFrameId = requestAnimationFrame(fancamLoop);
}
animFrameId = requestAnimationFrame(fancamLoop);

playBtn.addEventListener("click", () => {
  if (sourceVideo.paused) {
    sourceVideo.play();
    playIcon.style.display = "none";
    pauseIcon.style.display = "block";
  } else {
    sourceVideo.pause();
    playIcon.style.display = "block";
    pauseIcon.style.display = "none";
  }
});

muteBtn.addEventListener("click", () => {
  sourceVideo.muted = !sourceVideo.muted;
  muteBtn.style.opacity = sourceVideo.muted ? "0.5" : "1.0";
});

sourceVideo.addEventListener("timeupdate", () => {
  updateVirtualFancam();
  updateSeekBar();
});

seekBar.addEventListener("input", (e) => {
  const val = parseFloat(e.target.value);
  if (sourceVideo.duration) {
    sourceVideo.currentTime = (val / 100) * sourceVideo.duration;
    updateVirtualFancam();
  }
});

function updateSeekBar() {
  if (!sourceVideo.duration) return;
  const cur = sourceVideo.currentTime;
  const dur = sourceVideo.duration;
  seekBar.value = (cur / dur) * 100;
  curTimeText.textContent = formatTime(cur);
  durTimeText.textContent = formatTime(dur);
}

function formatTime(sec) {
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60);
  return `${m}:${s < 10 ? "0" : ""}${s}`;
}

// 8. Auto Initialization: URL params, LocalStorage, or Latest Job
(async function initStudio() {
  const params = new URLSearchParams(window.location.search);
  const paramJobId = params.get("job_id");
  const storedJobId = localStorage.getItem("autofancam_last_job");

  if (paramJobId) {
    startJobMonitoring(paramJobId);
  } else if (storedJobId) {
    startJobMonitoring(storedJobId);
  } else {
    // Check if there is a latest completed job on disk
    try {
      const res = await fetch("/api/jobs/latest");
      if (res.ok) {
        const data = await res.json();
        if (data.job_id) {
          startJobMonitoring(data.job_id);
        }
      }
    } catch (_) {}
  }
})();
