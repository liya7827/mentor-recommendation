document.addEventListener("DOMContentLoaded", () => {
    const getBaseUrl = () => {
        const script = document.querySelector('script[data-api-url]');
        if (script && script.dataset.apiUrl) {
            return script.dataset.apiUrl;
        }
        if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1') {
            return 'http://127.0.0.1:5000';
        }
        return 'https://liyaasdfg.pythonanywhere.com';
    };
    
    const BASE_URL = getBaseUrl();
    const AI_FAVORITES_URL = `${BASE_URL}/api/ai/favorites`;
    const FAVORITES_KEY = "favoriteMentors";
    const AI_ERROR_MESSAGE = "智能服务暂时不可用，请稍后重试";
    const AI_TIMEOUT_MESSAGE = "智能建议生成时间较长，请稍后重试或减少对比导师数量。";
    const AI_LOADING_MESSAGE = "智能建议正在生成，请稍候...";

    const favoriteContainer = document.getElementById("favoriteMentorsContainer");
    const favoriteCount = document.getElementById("favoriteCount");
    const btnFavoriteAdvice = document.getElementById("btnFavoriteAdvice");
    const favoriteAdviceBox = document.getElementById("favoriteAdviceBox");

    let favoriteMentors = loadFavorites();
    let selectedIds = new Set();

    renderFavorites();

    favoriteContainer.addEventListener("click", (event) => {
        const button = event.target.closest("button[data-action]");
        if (!button) {
            return;
        }
        const mentorId = button.dataset.id;
        if (button.dataset.action === "remove-favorite") {
            removeFavorite(mentorId);
        }
        if (button.dataset.action === "toggle-select") {
            toggleSelect(mentorId);
        }
    });

    btnFavoriteAdvice.addEventListener("click", async () => {
        const selectedMentors = getSelectedMentors();
        if (selectedMentors.length < 2 || selectedMentors.length > 3) {
            showAdvice(favoriteAdviceBox, "请选择 2-3 位心仪导师生成智能择师建议");
            return;
        }
        await requestFavoriteAdvice(selectedMentors);
    });

    function renderFavorites() {
        favoriteContainer.innerHTML = "";
        favoriteCount.innerText = favoriteMentors.length;
        btnFavoriteAdvice.disabled = favoriteMentors.length < 2;

        if (favoriteMentors.length === 0) {
            renderEmpty(favoriteContainer, "暂未添加心仪导师，请先从推荐结果中选择。");
            return;
        }

        favoriteMentors.forEach((mentor) => {
            const mentorId = mentorKey(mentor);
            const homepage = safeText(mentor.homepage_url);
            const selected = selectedIds.has(mentorId);
            const homepageButton = homepage
                ? `<a class="btn btn-outline-secondary btn-sm" href="${escapeAttr(homepage)}" target="_blank" rel="noopener noreferrer">查看主页</a>`
                : `<button class="btn btn-outline-secondary btn-sm" disabled>查看主页</button>`;
            const favoriteHTML = `
                <div class="col-12 col-xl-6 mb-3">
                    <article class="card favorite-card bg-white">
                        <div class="card-body p-3">
                            <div class="d-flex justify-content-between align-items-start gap-3 mb-2">
                                <div class="min-width-0">
                                    <h6 class="fw-bold mb-2 text-break">${escapeHtml(mentor.name || "未公开")}
                                        <span class="badge bg-light text-dark ms-2 fw-normal border">${escapeHtml(mentor.title || "未公开")}</span>
                                    </h6>
                                    <div class="badge-row">
                                        <span class="badge school-badge rounded-pill">${escapeHtml(mentor.school || "未公开")}</span>
                                        <span class="badge school-badge rounded-pill">${escapeHtml(mentor.province || "未公开")}</span>
                                        <span class="badge school-badge rounded-pill">${escapeHtml(mentor.college || "未公开")}</span>
                                    </div>
                                </div>
                                <div class="score-box favorite-score">
                                    <span class="text-theme fw-bold">${formatScore(mentor.score)}</span><br>
                                    <span class="text-muted small">匹配度</span>
                                </div>
                            </div>
                            <p class="small mentor-text mb-3"><strong>研究方向：</strong>${escapeHtml(mentor.area || "未公开")}</p>
                            <div class="mentor-actions d-flex gap-2 flex-wrap p-2 rounded">
                                ${homepageButton}
                                <button class="btn btn-danger-soft btn-sm" type="button" data-action="remove-favorite" data-id="${escapeAttr(mentorId)}">移除收藏</button>
                                <button class="btn ${selected ? "btn-compare-active" : "btn-outline-compare"} btn-sm" type="button" data-action="toggle-select" data-id="${escapeAttr(mentorId)}">${selected ? "取消选择" : "选择建议"}</button>
                            </div>
                        </div>
                    </article>
                </div>
            `;
            favoriteContainer.insertAdjacentHTML("beforeend", favoriteHTML);
        });
    }

    function renderEmpty(container, message) {
        container.innerHTML = `
            <div class="col-12 text-center text-muted mt-5 pt-5 empty-state">
                <p class="mt-2">${escapeHtml(message)}</p>
            </div>
        `;
    }

    function removeFavorite(mentorId) {
        favoriteMentors = favoriteMentors.filter((item) => mentorKey(item) !== mentorId);
        selectedIds.delete(mentorId);
        saveFavorites();
        renderFavorites();
    }

    function toggleSelect(mentorId) {
        if (selectedIds.has(mentorId)) {
            selectedIds.delete(mentorId);
        } else {
            if (selectedIds.size >= 3) {
                alert("最多只能选择 3 位导师生成建议");
                return;
            }
            selectedIds.add(mentorId);
        }
        renderFavorites();
    }

    async function requestFavoriteAdvice(mentors) {
        const originalHTML = btnFavoriteAdvice.innerHTML;
        btnFavoriteAdvice.disabled = true;
        btnFavoriteAdvice.innerHTML = `<span class="spinner-border spinner-border-sm me-1"></span>${escapeHtml(AI_LOADING_MESSAGE)}`;
        showAdvice(favoriteAdviceBox, AI_LOADING_MESSAGE);
        try {
            const response = await fetch(AI_FAVORITES_URL, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ mentors: mentors.slice(0, 3).map(toAiMentorPayload) }),
            });
            const payload = await parseJsonResponse(response);
            console.log("/api/ai/favorites response", payload);
            if (!response.ok || !payload.success) {
                throw new Error(payload.message || AI_ERROR_MESSAGE);
            }
            showAdvice(favoriteAdviceBox, payload.advice || AI_ERROR_MESSAGE);
        } catch (error) {
            showAdvice(favoriteAdviceBox, displayMessage(error.message) || AI_TIMEOUT_MESSAGE);
        } finally {
            btnFavoriteAdvice.disabled = favoriteMentors.length < 2;
            btnFavoriteAdvice.innerHTML = originalHTML;
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

    function getSelectedMentors() {
        return favoriteMentors.filter((mentor) => selectedIds.has(mentorKey(mentor)));
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

    window.favoritePageTest = {
        getFavorites: () => [...favoriteMentors],
        removeFavorite,
        toggleSelect,
        getSelectedMentors,
    };
});
