document.addEventListener("DOMContentLoaded", () => {
    const getBaseUrl = () => {
        const script = document.querySelector('script[data-api-url]');
        if (script && script.dataset.apiUrl) {
            return script.dataset.apiUrl;
        }
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return 'http://127.0.0.1:5000';
        }
        return 'return 'https://liyaasdfg.pythonanywhere.com';';
    };
    
    const BASE_URL = getBaseUrl();
    const API_URL = `${BASE_URL}/api/match`;
    const AI_COMPARE_URL = `${BASE_URL}/api/ai/compare`;
    const FAVORITES_KEY = "favoriteMentors";
    const AI_ERROR_MESSAGE = "智能服务暂时不可用，请稍后重试";
    const AI_TIMEOUT_MESSAGE = "智能建议生成时间较长，请稍后重试或减少对比导师数量。";
    const AI_LOADING_MESSAGE = "智能建议正在生成，请稍候...";

    const form = document.getElementById("recommendForm");
    const submitBtn = document.getElementById("submitBtn");
    const btnText = document.getElementById("btnText");
    const loadingSpinner = document.getElementById("loadingSpinner");
    const resultsContainer = document.getElementById("resultsContainer");
    const resultStatus = document.getElementById("resultStatus");
    const btnShowCompare = document.getElementById("btnShowCompare");
    const compareCountSpan = document.getElementById("compareCount");
    const compareTable = document.getElementById("compareTable");
    const btnCompareAdvice = document.getElementById("btnCompareAdvice");
    const compareAdviceBox = document.getElementById("compareAdviceBox");
    const compareModal = new bootstrap.Modal(document.getElementById("compareModal"));

    let currentMentors = [];
    let favoriteMentors = loadFavorites();
    let compareList = [];

    updateCompareBtn();

    form.addEventListener("submit", async (event) => {
        event.preventDefault();

        const requestData = {
            province: document.getElementById("provinceInput").value.trim(),
            title: document.getElementById("titleInput").value.trim(),
            expected_direction: document.getElementById("directionInput").value.trim(),
        };

        if (!requestData.expected_direction) {
            resultStatus.textContent = "请填写研究方向";
            return;
        }

        currentMentors = [];
        compareList = [];
        resultsContainer.innerHTML = "";
        updateCompareBtn();
        setLoading(true);
        resultStatus.textContent = "正在匹配导师";

        try {
            const response = await fetch(API_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify(requestData),
            });
            const payload = await response.json();
            if (!response.ok || !payload.success) {
                throw new Error(payload.message || "匹配请求失败");
            }

            currentMentors = Array.isArray(payload.recommendations) ? payload.recommendations : [];
            renderCards();
            resultStatus.textContent = `${payload.message}，共 ${currentMentors.length} 位导师`;
        } catch (error) {
            currentMentors = [];
            renderEmpty(resultsContainer, `请求失败：${error.message}`);
            resultStatus.textContent = "请求失败";
        } finally {
            setLoading(false);
        }
    });

    resultsContainer.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) {
            return;
        }
        const mentorId = button.dataset.id;
        if (button.dataset.action === "toggle-favorite") {
            const mentor = findMentor(mentorId);
            if (mentor) {
                toggleFavorite(mentor);
            }
        }
        if (button.dataset.action === "toggle-compare") {
            toggleCompare(mentorId);
        }
    });

    btnShowCompare.addEventListener("click", () => {
        const selectedMentors = getSelectedMentors();
        compareAdviceBox.classList.add("d-none");
        compareAdviceBox.innerText = "";
        compareTable.innerHTML = `
            <thead>
                <tr>
                    <th class="text-end text-muted">对比维度</th>
                    ${selectedMentors.map((mentor) => `<th><span class="fs-5">${escapeHtml(mentor.name || "未公开")}</span><br><small class="text-muted">${escapeHtml(mentor.title || "未公开")}</small></th>`).join("")}
                </tr>
            </thead>
            <tbody>
                ${compareRow("匹配度", selectedMentors.map((mentor) => formatScore(mentor.score)))}
                ${compareRow("任职高校", selectedMentors.map((mentor) => safeText(mentor.school) || "未公开"))}
                ${compareRow("所在地区", selectedMentors.map((mentor) => safeText(mentor.province) || "未公开"))}
                ${compareRow("所属院系", selectedMentors.map((mentor) => safeText(mentor.college) || "未公开"))}
                ${compareRow("导师职称", selectedMentors.map((mentor) => safeText(mentor.title) || "未公开"))}
                ${compareRow("研究方向", selectedMentors.map((mentor) => safeText(mentor.area) || "未公开"))}
            </tbody>
        `;
        compareModal.show();
    });

    btnCompareAdvice.addEventListener("click", async () => {
        const selectedMentors = getSelectedMentors();
        if (selectedMentors.length < 2 || selectedMentors.length > 3) {
            showAdvice(compareAdviceBox, "请选择 2-3 位导师进行智能对比");
            return;
        }
        await requestAiAdvice({
            url: AI_COMPARE_URL,
            mentors: selectedMentors,
            button: btnCompareAdvice,
            box: compareAdviceBox,
        });
    });

    function setLoading(isLoading) {
        submitBtn.disabled = isLoading;
        loadingSpinner.classList.toggle("d-none", !isLoading);
        btnText.innerText = isLoading ? "算法匹配中" : "重新匹配";
    }

    function renderCards() {
        resultsContainer.innerHTML = "";
        if (currentMentors.length === 0) {
            renderEmpty(resultsContainer, "没有符合条件的导师");
            return;
        }

        currentMentors.forEach((mentor) => {
            const mentorId = mentorKey(mentor);
            const isFavorite = favoriteMentors.some((item) => mentorKey(item) === mentorId);
            const inCompare = compareList.includes(mentorId);
            const homepage = safeText(mentor.homepage_url);
            const homepageButton = homepage
                ? `<a class="btn btn-outline-secondary btn-sm" href="${escapeAttr(homepage)}" target="_blank" rel="noopener noreferrer">主页</a>`
                : `<button class="btn btn-outline-secondary btn-sm" disabled>主页</button>`;

            const cardHTML = `
                <div class="col-12 mb-3">
                    <article class="card mentor-card bg-white">
                        <div class="card-body p-4">
                            <div class="d-flex justify-content-between align-items-start gap-3">
                                <div class="min-width-0">
                                    <h5 class="fw-bold mb-2 text-break">${escapeHtml(mentor.name || "未公开")}
                                        <span class="badge bg-light text-dark ms-2 fw-normal border">${escapeHtml(mentor.title || "未公开")}</span>
                                    </h5>
                                    <div class="badge-row">
                                        <span class="badge school-badge rounded-pill">${escapeHtml(mentor.school || "未公开")}</span>
                                        <span class="badge school-badge rounded-pill">${escapeHtml(mentor.province || "未公开")}</span>
                                        ${mentor.college ? `<span class="badge school-badge rounded-pill">${escapeHtml(mentor.college)}</span>` : ""}
                                    </div>
                                </div>
                                <div class="text-end score-box">
                                    <span class="text-theme fw-bold fs-5">${formatScore(mentor.score)}</span><br>
                                    <span class="text-muted small">匹配度</span>
                                </div>
                            </div>
                            <hr class="text-muted opacity-25">
                            <p class="mb-2 small mentor-text"><strong>研究方向：</strong>${escapeHtml(mentor.area || "未公开")}</p>
                            <p class="mb-2 small mentor-text ai-reason"><strong>推荐理由：</strong>${escapeHtml(mentor.match_reason || "暂无智能推荐理由")}</p>
                            <p class="mb-2 small mentor-text"><strong>邮箱：</strong>${escapeHtml(mentor.email || "未公开")}</p>
                            <div class="mentor-actions d-flex justify-content-between align-items-center p-2 rounded mt-3 flex-wrap gap-2">
                                <div class="d-flex gap-2 flex-wrap">
                                    ${homepageButton}
                                    <button class="btn ${isFavorite ? "btn-theme" : "btn-outline-success"} btn-sm" type="button" data-action="toggle-favorite" data-id="${escapeAttr(mentorId)}">
                                        ${isFavorite ? "取消心仪" : "加入心仪导师"}
                                    </button>
                                </div>
                                <button class="btn ${inCompare ? "btn-compare-active" : "btn-outline-compare"} btn-sm" type="button" data-action="toggle-compare" data-id="${escapeAttr(mentorId)}">
                                    ${inCompare ? "取消对比" : "加入横向对比"}
                                </button>
                            </div>
                        </div>
                    </article>
                </div>
            `;
            resultsContainer.insertAdjacentHTML("beforeend", cardHTML);
        });
    }

    function renderEmpty(container, message) {
        container.innerHTML = `
            <div class="col-12 text-center text-muted mt-4 mb-3 empty-state">
                <p class="mt-2">${escapeHtml(message)}</p>
            </div>
        `;
    }

    function toggleFavorite(mentor) {
        const mentorId = mentorKey(mentor);
        if (favoriteMentors.some((item) => mentorKey(item) === mentorId)) {
            favoriteMentors = favoriteMentors.filter((item) => mentorKey(item) !== mentorId);
        } else {
            favoriteMentors.push(normalizeMentor(mentor));
        }
        saveFavorites();
        renderCards();
    }

    function toggleCompare(mentorId) {
        if (compareList.includes(mentorId)) {
            compareList = compareList.filter((id) => id !== mentorId);
        } else {
            if (compareList.length >= 3) {
                alert("最多只能同时对比 3 位导师");
                return false;
            }
            compareList.push(mentorId);
        }
        renderCards();
        updateCompareBtn();
        return true;
    }

    function updateCompareBtn() {
        compareCountSpan.innerText = compareList.length;
        btnShowCompare.disabled = compareList.length < 2;
        btnShowCompare.classList.toggle("btn-compare-active", compareList.length >= 2);
        btnShowCompare.classList.toggle("btn-compare-disabled", compareList.length < 2);
    }

    function compareRow(label, values) {
        return `
            <tr>
                <td class="text-end fw-bold text-muted bg-light">${escapeHtml(label)}</td>
                ${values.map((value) => `<td class="text-break">${escapeHtml(value)}</td>`).join("")}
            </tr>
        `;
    }

    function getSelectedMentors() {
        return compareList.map((id) => findMentor(id)).filter(Boolean);
    }

    async function requestAiAdvice({ url, mentors, button, box }) {
        const originalHTML = button.innerHTML;
        button.disabled = true;
        button.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${escapeHtml(AI_LOADING_MESSAGE)}`;
        showAdvice(box, AI_LOADING_MESSAGE);
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mentors: mentors.slice(0, 3).map(toAiMentorPayload) }),
            });
            const payload = await parseJsonResponse(response);
            console.log("/api/ai/compare response", payload);
            if (!response.ok || !payload.success) {
                throw new Error(payload.message || AI_ERROR_MESSAGE);
            }
            showAdvice(box, payload.advice || AI_ERROR_MESSAGE);
        } catch (error) {
            showAdvice(box, displayMessage(error.message) || AI_TIMEOUT_MESSAGE);
        } finally {
            button.disabled = false;
            button.innerHTML = originalHTML;
        }
    }

    function showAdvice(box, text) {
        box.classList.remove("d-none");
        box.innerText = text;
    }

    function displayMessage(message) {
        return safeText(message).replace(/^A[IＩ]\s*服务/, "智能服务");
    }

    async function parseJsonResponse(response) {
        const rawText = await response.text();
        try {
            return rawText ? JSON.parse(rawText) : {};
        } catch (error) {
            return { success: false, message: AI_ERROR_MESSAGE };
        }
    }

    function loadFavorites() {
        try {
            const raw = localStorage.getItem(FAVORITES_KEY);
            const parsed = raw ? JSON.parse(raw) : [];
            return Array.isArray(parsed) ? dedupeMentors(parsed.map(normalizeMentor)) : [];
        } catch (error) {
            return [];
        }
    }

    function saveFavorites() {
        favoriteMentors = dedupeMentors(favoriteMentors.map(normalizeMentor));
        localStorage.setItem(FAVORITES_KEY, JSON.stringify(favoriteMentors));
    }

    function dedupeMentors(mentors) {
        const seen = new Set();
        const unique = [];
        mentors.forEach((mentor) => {
            const key = mentorKey(mentor);
            if (key && !seen.has(key)) {
                seen.add(key);
                unique.push(mentor);
            }
        });
        return unique;
    }

    function normalizeMentor(mentor) {
        return {
            id: safeText(mentor.id),
            name: safeText(mentor.name),
            title: safeText(mentor.title),
            school: safeText(mentor.school),
            province: safeText(mentor.province),
            college: safeText(mentor.college),
            area: safeText(mentor.area),
            score: Number(mentor.score) || 0,
            email: safeText(mentor.email),
            homepage_url: safeText(mentor.homepage_url),
            match_reason: safeText(mentor.match_reason),
        };
    }

    function toAiMentorPayload(mentor) {
        return {
            name: safeText(mentor.name),
            title: safeText(mentor.title),
            school: safeText(mentor.school),
            province: safeText(mentor.province),
            college: safeText(mentor.college),
            area: safeText(mentor.area).slice(0, 180),
            score: Number(mentor.score) || 0,
        };
    }

    function mentorKey(mentor) {
        const id = safeText(mentor.id);
        if (id) {
            return id;
        }
        return [mentor.name, mentor.school, mentor.title, mentor.area].map(safeText).join("|");
    }

    function findMentor(mentorId) {
        return currentMentors.find((mentor) => mentorKey(mentor) === mentorId);
    }

    function formatScore(score) {
        const numericScore = Number(score);
        if (!Number.isFinite(numericScore)) {
            return "0.0%";
        }
        const percent = numericScore <= 1 ? numericScore * 100 : numericScore;
        return `${percent.toFixed(1)}%`;
    }

    function safeText(value) {
        return value === null || value === undefined ? "" : String(value).trim();
    }

    function escapeHtml(value) {
        return safeText(value).replace(/[&<>"']/g, (char) => ({
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#39;",
        }[char]));
    }

    function escapeAttr(value) {
        return escapeHtml(value).replace(/`/g, "&#96;");
    }

    window.mentorAppTest = {
        addFavorite: (mentor) => { favoriteMentors.push(normalizeMentor(mentor)); saveFavorites(); renderCards(); },
        toggleFavorite,
        getFavorites: () => [...favoriteMentors],
        addToCompare: (mentorId) => toggleCompare(mentorId),
        getCompareList: () => [...compareList],
    };
});
