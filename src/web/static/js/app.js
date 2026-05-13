/**
 * UMU Advanced - Frontend Application Logic
 */

(function() {
    'use strict';

    // Current auth state
    let authState = { logged_in: false, username: null, is_admin: false };
    let activeEventSource = null;
    let currentRunId = '';
    let selectedRunStatus = '';
    let isGovernanceRunning = false;
    let resultsModalPreviousTab = 'new';

    // History table state
    let historyRuns = [];
    let historyFiltered = [];
    let historyPage = 1;
    let historyPageSize = 10;

    /**
     * SVG icon markup per badge level.
     */
    function badgeIconSvg(level) {
        if (level === 'ok') {
            return '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>';
        }
        if (level === 'major') {
            return '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';
        }
        if (level === 'minor') {
            return '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
        }
        return '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>';
    }

    // DOM element references
    const els = {
        currentUser: document.getElementById('currentUser'),
        adminBadge: document.getElementById('adminBadge'),
        logoutBtn: document.getElementById('logoutBtn'),
        pageTitle: document.getElementById('pageTitle'),
        usersPage: document.getElementById('usersPage'),
        coursesPage: document.getElementById('coursesPage'),
        governancePage: document.getElementById('governancePage'),
        nonAdminWarning: document.getElementById('nonAdminWarning'),
        syncUsersBtn: document.getElementById('syncUsersBtn'),
        syncCoursesBtn: document.getElementById('syncCoursesBtn'),
        startGovernanceBtn: document.getElementById('startGovernanceBtn'),
        quickGovernanceBtn: document.getElementById('quickGovernanceBtn'),
        governanceStartDate: document.getElementById('governanceStartDate'),
        governanceEndDate: document.getElementById('governanceEndDate'),
        usersProgress: document.getElementById('usersProgress'),
        coursesProgress: document.getElementById('coursesProgress'),
        governanceProgress: document.getElementById('governanceProgress'),
        usersProgressFill: document.getElementById('usersProgressFill'),
        coursesProgressFill: document.getElementById('coursesProgressFill'),
        governanceProgressFill: document.getElementById('governanceProgressFill'),
        usersProgressInfo: document.getElementById('usersProgressInfo'),
        coursesProgressInfo: document.getElementById('coursesProgressInfo'),
        governanceProgressInfo: document.getElementById('governanceProgressInfo'),
        governanceStats: document.getElementById('resultsStats'),
        governanceResults: document.getElementById('governanceResults'),
        governanceResultsBody: document.getElementById('governanceResultsBody'),
        statTotal: document.getElementById('statTotal'),
        statCompliant: document.getElementById('statCompliant'),
        statMajor: document.getElementById('statMajor'),
        governanceLiveStats: document.getElementById('governanceLiveStats'),
        liveTotal: document.getElementById('liveTotal'),
        liveProgress: document.getElementById('liveProgress'),
        liveCompliant: document.getElementById('liveCompliant'),
        liveMajor: document.getElementById('liveMajor'),
        navItems: document.querySelectorAll('.nav-item'),
        governanceConfigPage: document.getElementById('governanceConfigPage'),
        saveConfigBtn: document.getElementById('saveConfigBtn'),
        resetConfigBtn: document.getElementById('resetConfigBtn'),
        backupConfigBtn: document.getElementById('backupConfigBtn'),
        restoreConfigBtn: document.getElementById('restoreConfigBtn'),
        configFileInput: document.getElementById('configFileInput'),
        configMessage: document.getElementById('configMessage'),
        forbiddenWords: document.getElementById('forbiddenWords'),
        exceptionWords: document.getElementById('exceptionWords'),
        fallbackForbiddenWords: document.getElementById('fallbackForbiddenWords'),
        validCategories: document.getElementById('validCategories'),
        evaluationKeywords: document.getElementById('evaluationKeywords'),
        meaninglessPlaceholders: document.getElementById('meaninglessPlaceholders'),
        emptyContentMarker: document.getElementById('emptyContentMarker'),
        excludedUmuId: document.getElementById('excludedUmuId'),
        excludedLessonType: document.getElementById('excludedLessonType'),
        maxDurationHours: document.getElementById('maxDurationHours'),
        excludedCourseIds: document.getElementById('excludedCourseIds'),
        courseStartDate: document.getElementById('courseStartDate'),
        courseEndDate: document.getElementById('courseEndDate'),
        exportResultsBtn: document.getElementById('exportResultsBtn'),
        // Governance tabs
        governanceTabs: document.querySelectorAll('.governance-tab'),
        governanceNewTab: document.getElementById('governanceNewTab'),
        governanceHistoryTab: document.getElementById('governanceHistoryTab'),
        governanceResultsTab: document.getElementById('governanceResultsTab'),
        // Preview panel
        refreshPreviewBtn: document.getElementById('refreshPreviewBtn'),
        quickDateTags: document.querySelectorAll('.quick-date-tag'),
        previewCourseCount: document.getElementById('previewCourseCount'),
        previewUserCount: document.getElementById('previewUserCount'),
        previewLastSync: document.getElementById('previewLastSync'),
        previewHint: document.getElementById('previewHint'),
        // Step indicator
        step1: document.getElementById('step1'),
        step2: document.getElementById('step2'),
        step3: document.getElementById('step3'),
        step4: document.getElementById('step4'),
        stepDetails: document.getElementById('stepDetails'),
        // History table
        historySearchInput: document.getElementById('historySearchInput'),
        historyStatusFilter: document.getElementById('historyStatusFilter'),
        historySortBy: document.getElementById('historySortBy'),
        historyTableBody: document.getElementById('historyTableBody'),
        historyTableContainer: document.getElementById('historyTableContainer'),
        historyEmptyState: document.getElementById('historyEmptyState'),
        historyPagination: document.getElementById('historyPagination'),
        historyPageInfo: document.getElementById('historyPageInfo'),
        historyPrevPage: document.getElementById('historyPrevPage'),
        historyNextPage: document.getElementById('historyNextPage'),
        // Results
        resultsFilterLevel: document.getElementById('resultsFilterLevel'),
        resultsFilterRule: document.getElementById('resultsFilterRule'),
        resultsEmptyState: document.getElementById('resultsEmptyState'),
        resultsAllCompliantState: document.getElementById('resultsAllCompliantState'),
        resumeGovernanceBtn: document.getElementById('resumeGovernanceBtn'),
        // Results modal
        resultsModalOverlay: document.getElementById('resultsModalOverlay'),
        resultsModalClose: document.getElementById('resultsModalClose'),
        // Governance progress modal (blocking)
        governanceProgressModal: document.getElementById('governanceProgressModal'),
        // Drawer
        drawerOverlay: document.getElementById('drawerOverlay'),
        courseDrawer: document.getElementById('courseDrawer'),
        drawerClose: document.getElementById('drawerClose'),
        drawerCloseBtn: document.getElementById('drawerCloseBtn'),
        drawerTitle: document.getElementById('drawerTitle'),
        drawerBasicInfo: document.getElementById('drawerBasicInfo'),
        drawerRuleDetails: document.getElementById('drawerRuleDetails'),
        drawerEditLink: document.getElementById('drawerEditLink'),
    };

    /**
     * Initialize the application
     */
    async function init() {
        await loadAuthStatus();
        if (!authState.logged_in) {
            window.location.href = '/login';
            return;
        }
        setupEventListeners();
        updateUIForAuth();
        setDefaultCourseDates();

        // Restore page from URL hash, or stay on default (governance)
        var hashPage = window.location.hash.slice(1);
        var validPages = ['governance', 'users', 'courses', 'governance-config'];
        if (hashPage && validPages.indexOf(hashPage) !== -1) {
            switchPage(hashPage);
        } else {
            var subtitleEl = document.getElementById('pageSubtitle');
            if (subtitleEl) subtitleEl.textContent = '按照 8 条规则审核本地课程数据合规性';
        }

        window.addEventListener('hashchange', function() {
            var newPage = window.location.hash.slice(1);
            if (newPage && validPages.indexOf(newPage) !== -1) {
                switchPage(newPage);
            }
        });
    }

    /**
     * Set default date range for course sync (Jan 1st of current year to today)
     */
    function setDefaultCourseDates() {
        if (!els.courseStartDate || !els.courseEndDate) {
            return;
        }
        var now = new Date();
        var year = now.getFullYear();
        var month = String(now.getMonth() + 1).padStart(2, '0');
        var day = String(now.getDate()).padStart(2, '0');
        var todayStr = year + '-' + month + '-' + day;
        var janFirstStr = year + '-01-01';

        if (!els.courseStartDate.value) {
            els.courseStartDate.value = janFirstStr;
        }
        if (!els.courseEndDate.value) {
            els.courseEndDate.value = todayStr;
        }
        if (els.governanceStartDate && !els.governanceStartDate.value) {
            els.governanceStartDate.value = janFirstStr;
        }
        if (els.governanceEndDate && !els.governanceEndDate.value) {
            els.governanceEndDate.value = todayStr;
        }
        refreshStartGovernanceBtn();
        loadPreview();
    }

    /**
     * Load authentication status from the server
     */
    async function loadAuthStatus() {
        try {
            const response = await fetch('/api/auth/status');
            const data = await response.json();
            authState = {
                logged_in: data.logged_in || false,
                username: data.username || null,
                is_admin: data.is_admin || false,
            };
        } catch (err) {
            authState = { logged_in: false, username: null, is_admin: false };
        }
    }

    /**
     * Update UI elements based on authentication state
     */
    function updateUIForAuth() {
        if (els.currentUser) {
            els.currentUser.textContent = authState.username || '未知用户';
        }
        if (els.adminBadge) {
            var wasHidden = els.adminBadge.classList.contains('hidden');
            els.adminBadge.classList.toggle('hidden', !authState.is_admin);
            if (wasHidden && authState.is_admin) {
                els.adminBadge.classList.add('admin-badge-animated');
                setTimeout(function() {
                    els.adminBadge.classList.remove('admin-badge-animated');
                }, 500);
            }
        }

        const isAdmin = authState.is_admin;

        if (els.nonAdminWarning) {
            els.nonAdminWarning.classList.toggle('hidden', isAdmin);
        }

        setButtonEnabled(els.syncUsersBtn, isAdmin);
        setButtonEnabled(els.syncCoursesBtn, isAdmin);
        refreshStartGovernanceBtn();
        setButtonEnabled(els.saveConfigBtn, isAdmin);
        setButtonEnabled(els.resetConfigBtn, isAdmin);
        if (els.resumeGovernanceBtn) {
            var canResume = currentRunId && selectedRunStatus === 'interrupted';
            els.resumeGovernanceBtn.disabled = !isAdmin || !canResume;
            els.resumeGovernanceBtn.classList.toggle('hidden', !canResume);
            if (els.startGovernanceBtn && canResume) {
                els.startGovernanceBtn.disabled = true;
            }
        }
    }

    /**
     * Enable or disable a sync button
     */
    function setButtonEnabled(btn, enabled) {
        if (!btn) return;
        btn.disabled = !enabled;
    }

    /**
     * Enable or disable all governance page controls
     */
    function setGovernanceControlsEnabled(enabled) {
        var effective = enabled && authState.is_admin;
        if (els.governanceStartDate) els.governanceStartDate.disabled = !effective;
        if (els.governanceEndDate) els.governanceEndDate.disabled = !effective;
        if (enabled) {
            refreshStartGovernanceBtn();
        } else {
            setButtonEnabled(els.startGovernanceBtn, false);
            setButtonEnabled(els.quickGovernanceBtn, false);
        }
        if (els.resumeGovernanceBtn) {
            if (!enabled) {
                els.resumeGovernanceBtn.classList.add('hidden');
            } else {
                var canResume = currentRunId && selectedRunStatus === 'interrupted';
                els.resumeGovernanceBtn.disabled = !canResume || !authState.is_admin;
                els.resumeGovernanceBtn.classList.toggle('hidden', !canResume);
            }
        }
    }

    /**
     * Whether both governance date inputs are filled
     */
    function governanceDatesAreValid() {
        var start = els.governanceStartDate ? els.governanceStartDate.value : '';
        var end = els.governanceEndDate ? els.governanceEndDate.value : '';
        return Boolean(start && end);
    }

    /**
     * Sync start-governance button state with admin status and date inputs.
     */
    function refreshStartGovernanceBtn() {
        if (!els.startGovernanceBtn) return;
        var baseEnabled = authState.is_admin && governanceDatesAreValid();
        var hasInterrupted = currentRunId && selectedRunStatus === 'interrupted';
        els.startGovernanceBtn.disabled = !baseEnabled || hasInterrupted;
        if (els.quickGovernanceBtn) {
            els.quickGovernanceBtn.disabled = !baseEnabled || hasInterrupted;
        }
    }

    /**
     * Setup all event listeners
     */
    function setupEventListeners() {
        // Navigation
        els.navItems.forEach(function(item) {
            item.addEventListener('click', function(e) {
                e.preventDefault();
                const page = item.getAttribute('data-page');
                if (page) {
                    switchPage(page);
                }
            });
        });

        // Logout
        if (els.logoutBtn) {
            els.logoutBtn.addEventListener('click', handleLogout);
        }

        // Sync buttons
        if (els.syncUsersBtn) {
            els.syncUsersBtn.addEventListener('click', function() {
                startSync('users');
            });
        }
        if (els.syncCoursesBtn) {
            els.syncCoursesBtn.addEventListener('click', function() {
                startSync('courses');
            });
        }
        if (els.startGovernanceBtn) {
            els.startGovernanceBtn.addEventListener('click', startGovernance);
        }
        if (els.quickGovernanceBtn) {
            els.quickGovernanceBtn.addEventListener('click', quickGovernance);
        }
        if (els.governanceStartDate) {
            els.governanceStartDate.addEventListener('change', function() {
                refreshStartGovernanceBtn();
                loadPreview();
            });
            els.governanceStartDate.addEventListener('input', refreshStartGovernanceBtn);
        }
        if (els.governanceEndDate) {
            els.governanceEndDate.addEventListener('change', function() {
                refreshStartGovernanceBtn();
                loadPreview();
            });
            els.governanceEndDate.addEventListener('input', refreshStartGovernanceBtn);
        }

        // Governance tabs
        els.governanceTabs.forEach(function(tab) {
            tab.addEventListener('click', function() {
                switchGovernanceTab(tab.dataset.tab);
            });
        });

        // Quick date tags
        els.quickDateTags.forEach(function(tag) {
            tag.addEventListener('click', function() {
                applyQuickDate(tag.dataset.range);
            });
        });

        // Refresh preview
        if (els.refreshPreviewBtn) {
            els.refreshPreviewBtn.addEventListener('click', loadPreview);
        }

        // History filters
        if (els.historySearchInput) {
            els.historySearchInput.addEventListener('input', debounce(filterHistory, 200));
        }
        if (els.historyStatusFilter) {
            els.historyStatusFilter.addEventListener('change', filterHistory);
        }
        if (els.historySortBy) {
            els.historySortBy.addEventListener('change', filterHistory);
        }
        if (els.historyPrevPage) {
            els.historyPrevPage.addEventListener('click', function() {
                if (historyPage > 1) {
                    historyPage--;
                    renderHistoryPage();
                }
            });
        }
        if (els.historyNextPage) {
            els.historyNextPage.addEventListener('click', function() {
                var maxPage = Math.ceil(historyFiltered.length / historyPageSize);
                if (historyPage < maxPage) {
                    historyPage++;
                    renderHistoryPage();
                }
            });
        }

        // Results filter
        if (els.resultsFilterLevel) {
            els.resultsFilterLevel.addEventListener('change', function() {
                if (currentRunId) {
                    loadGovernanceResults(currentRunId);
                }
            });
        }
        if (els.resultsFilterRule) {
            els.resultsFilterRule.addEventListener('change', function() {
                if (currentRunId) {
                    loadGovernanceResults(currentRunId);
                }
            });
        }

        // Drawer close handlers
        if (els.drawerClose) {
            els.drawerClose.addEventListener('click', closeDrawer);
        }
        if (els.drawerCloseBtn) {
            els.drawerCloseBtn.addEventListener('click', closeDrawer);
        }
        if (els.drawerOverlay) {
            els.drawerOverlay.addEventListener('click', closeDrawer);
        }
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                if (els.drawerOverlay && els.drawerOverlay.classList.contains('active')) {
                    closeDrawer();
                } else if (els.resultsModalOverlay && els.resultsModalOverlay.classList.contains('active')) {
                    closeResultsModal();
                }
            }
        });

        if (els.exportResultsBtn) {
            els.exportResultsBtn.addEventListener('click', function() {
                if (!currentRunId) {
                    showToast('暂无可导出的治理结果', 'warning');
                    return;
                }
                var url = '/api/governance/runs/' + currentRunId + '/export';
                var a = document.createElement('a');
                a.href = url;
                a.style.display = 'none';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            });
        }
        if (els.resumeGovernanceBtn) {
            els.resumeGovernanceBtn.addEventListener('click', resumeGovernance);
        }
        // Results modal
        if (els.resultsModalOverlay) {
            els.resultsModalOverlay.addEventListener('click', function(e) {
                if (e.target === els.resultsModalOverlay) closeResultsModal();
            });
        }
        if (els.resultsModalClose) {
            els.resultsModalClose.addEventListener('click', closeResultsModal);
        }
        if (els.saveConfigBtn) {
            els.saveConfigBtn.addEventListener('click', saveGovernanceConfig);
        }
        if (els.backupConfigBtn) {
            els.backupConfigBtn.addEventListener('click', backupGovernanceConfig);
        }
        if (els.restoreConfigBtn) {
            els.restoreConfigBtn.addEventListener('click', function() {
                if (els.configFileInput) els.configFileInput.click();
            });
        }
        if (els.configFileInput) {
            els.configFileInput.addEventListener('change', restoreGovernanceConfig);
        }
        if (els.resetConfigBtn) {
            els.resetConfigBtn.addEventListener('click', resetGovernanceConfig);
        }
    }

    /**
     * Switch between governance sub-tabs
     */
    function switchGovernanceTab(tabName) {
        closeDrawer();
        closeResultsModal(false);

        els.governanceTabs.forEach(function(tab) {
            var isActive = tab.dataset.tab === tabName;
            tab.classList.toggle('active', isActive);
            tab.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        if (els.governanceNewTab) els.governanceNewTab.classList.toggle('hidden', tabName !== 'new');
        if (els.governanceHistoryTab) els.governanceHistoryTab.classList.toggle('hidden', tabName !== 'history');

        if (tabName === 'history') {
            loadGovernanceRuns();
        }
    }

    /**
     * Open the results analysis modal
     */
    function openResultsModal(runId) {
        if (els.governanceNewTab && !els.governanceNewTab.classList.contains('hidden')) {
            resultsModalPreviousTab = 'new';
        } else if (els.governanceHistoryTab && !els.governanceHistoryTab.classList.contains('hidden')) {
            resultsModalPreviousTab = 'history';
        }
        if (runId) loadGovernanceResults(runId);
        if (els.resultsModalOverlay) {
            els.resultsModalOverlay.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    /**
     * Close the results analysis modal
     */
    function closeResultsModal(switchTab) {
        if (els.resultsModalOverlay) {
            els.resultsModalOverlay.classList.remove('active');
            document.body.style.overflow = '';
        }
        if (switchTab !== false) {
            switchGovernanceTab(resultsModalPreviousTab);
        }
    }

    /**
     * Open the blocking governance progress modal.
     */
    function openGovernanceProgressModal() {
        if (els.governanceProgress) els.governanceProgress.classList.remove('hidden');
        if (els.governanceLiveStats) els.governanceLiveStats.classList.remove('hidden');
        if (els.governanceProgressModal) {
            els.governanceProgressModal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    /**
     * Close the blocking governance progress modal.
     * Body scroll is re-locked by openResultsModal when called immediately
     * after, so intermediate unlocking is not visible.
     */
    function closeGovernanceProgressModal() {
        if (els.governanceProgressModal) {
            els.governanceProgressModal.classList.remove('active');
        }
        var resultsOpen = els.resultsModalOverlay && els.resultsModalOverlay.classList.contains('active');
        if (!resultsOpen) {
            document.body.style.overflow = '';
        }
    }

    /**
     * Apply quick date range selection
     */
    function applyQuickDate(range) {
        var now = new Date();
        var year = now.getFullYear();
        var month = now.getMonth();
        var day = now.getDate();
        var startStr, endStr;

        if (range === 'month') {
            startStr = formatDate(new Date(year, month, 1));
            endStr = formatDate(now);
        } else if (range === 'last_month') {
            startStr = formatDate(new Date(year, month - 1, 1));
            endStr = formatDate(new Date(year, month, 0));
        } else if (range === 'quarter') {
            var quarterStart = Math.floor(month / 3) * 3;
            startStr = formatDate(new Date(year, quarterStart, 1));
            endStr = formatDate(now);
        } else if (range === 'year') {
            startStr = year + '-01-01';
            endStr = formatDate(now);
        } else if (range === 'all') {
            startStr = '2020-01-01';
            endStr = formatDate(now);
        }

        if (els.governanceStartDate) els.governanceStartDate.value = startStr;
        if (els.governanceEndDate) els.governanceEndDate.value = endStr;

        els.quickDateTags.forEach(function(tag) {
            var isActive = tag.dataset.range === range;
            tag.classList.toggle('active', isActive);
            if (isActive) {
                tag.classList.add('quick-date-tag-pressed');
                setTimeout(function() {
                    tag.classList.remove('quick-date-tag-pressed');
                }, 200);
            }
        });

        refreshStartGovernanceBtn();
        loadPreview();
    }

    /**
     * Format date as YYYY-MM-DD
     */
    function formatDate(d) {
        var y = d.getFullYear();
        var m = String(d.getMonth() + 1).padStart(2, '0');
        var day = String(d.getDate()).padStart(2, '0');
        return y + '-' + m + '-' + day;
    }

    /**
     * Load preview data for the selected date range
     */
    async function loadPreview() {
        if (!els.previewCourseCount || !els.previewUserCount) return;

        var start = els.governanceStartDate ? els.governanceStartDate.value : '';
        var end = els.governanceEndDate ? els.governanceEndDate.value : '';

        if (!start || !end) {
            els.previewCourseCount.textContent = '—';
            els.previewUserCount.textContent = '—';
            els.previewLastSync.textContent = '—';
            return;
        }

        setPreviewSkeleton(true);

        try {
            var url = '/api/governance/preview?start_date=' + encodeURIComponent(start) + '&end_date=' + encodeURIComponent(end);
            const response = await fetch(url);
            const data = await response.json();

            setPreviewSkeleton(false);

            if (data.success) {
                var courseCount = data.course_count !== undefined ? data.course_count : '—';
                var userCount = data.user_count !== undefined ? data.user_count : '—';
                var lastSync = data.last_sync || '—';

                if (typeof courseCount === 'number') {
                    animateNumber(els.previewCourseCount, courseCount, 500);
                } else {
                    els.previewCourseCount.textContent = courseCount;
                }
                if (typeof userCount === 'number') {
                    setTimeout(function() {
                        animateNumber(els.previewUserCount, userCount, 500);
                    }, 100);
                } else {
                    els.previewUserCount.textContent = userCount;
                }
                els.previewLastSync.textContent = lastSync;

                if (els.previewHint) {
                    var hint = '';
                    if (!data.last_sync) {
                        hint = '数据尚未同步，完整治理将自动同步用户和课程数据';
                    }
                    els.previewHint.textContent = hint;
                }
            }
        } catch (err) {
            setPreviewSkeleton(false);
            els.previewCourseCount.textContent = '—';
            els.previewUserCount.textContent = '—';
            els.previewLastSync.textContent = '—';
        }
    }

    /**
     * Switch between pages
     */
    async function switchPage(page) {
        closeDrawer();
        closeResultsModal(false);

        els.navItems.forEach(function(item) {
            var isActive = item.getAttribute('data-page') === page;
            item.classList.toggle('active', isActive);
            if (isActive) {
                item.setAttribute('aria-current', 'page');
            } else {
                item.removeAttribute('aria-current');
            }
        });

        var titles = {
            users: '更新用户列表',
            courses: '更新课程信息',
            governance: '培训数据治理',
            'governance-config': '治理规则配置',
        };
        var subtitles = {
            users: '从 UMU 平台同步企业用户数据到本地数据库',
            courses: '从 UMU 平台同步课程分组数据到本地数据库',
            governance: '按照 8 条规则审核本地课程数据合规性',
            'governance-config': '调整治理审核规则的参数',
        };
        if (els.pageTitle) els.pageTitle.textContent = titles[page] || '';
        var subtitleEl = document.getElementById('pageSubtitle');
        if (subtitleEl) subtitleEl.textContent = subtitles[page] || '';

        if (els.usersPage) {
            els.usersPage.classList.toggle('hidden', page !== 'users');
        }
        if (els.coursesPage) {
            els.coursesPage.classList.toggle('hidden', page !== 'courses');
        }
        if (els.governancePage) {
            els.governancePage.classList.toggle('hidden', page !== 'governance');
        }
        if (els.governanceConfigPage) {
            els.governanceConfigPage.classList.toggle('hidden', page !== 'governance-config');
        }

        if (page === 'governance') {
            await checkAndConnectActiveGovernance();
            loadPreview();
            // Default to new tab
            switchGovernanceTab('new');
        }
        if (page === 'governance-config') {
            loadGovernanceConfig();
        }

        history.replaceState(null, '', '#' + page);
    }

    /**
     * Handle logout
     */
    async function handleLogout() {
        try {
            await fetch('/api/logout', { method: 'POST' });
        } catch (err) {
            // ignore
        }
        window.location.href = '/login';
    }

    /**
     * Start a sync operation (users or courses)
     */
    async function startSync(type) {
        if (!authState.is_admin) {
            return;
        }

        const btn = type === 'users' ? els.syncUsersBtn : els.syncCoursesBtn;
        const progressContainer = type === 'users' ? els.usersProgress : els.coursesProgress;
        const progressFill = type === 'users' ? els.usersProgressFill : els.coursesProgressFill;
        const progressInfo = type === 'users' ? els.usersProgressInfo : els.coursesProgressInfo;

        if (progressFill) progressFill.style.width = '0%';
        if (progressInfo) progressInfo.textContent = '准备中...';
        if (progressContainer) progressContainer.classList.remove('hidden');

        setButtonLoading(btn, true);

        try {
            var body = {};
            if (type === 'courses') {
                body.start_date = els.courseStartDate ? els.courseStartDate.value : '';
                body.end_date = els.courseEndDate ? els.courseEndDate.value : '';
            }
            const response = await fetch('/api/sync/' + type + '/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            });
            const data = await response.json();

            if (data.success) {
                connectStatusStream(type);
            } else {
                if (progressInfo) progressInfo.textContent = data.error || '启动失败';
                setButtonLoading(btn, false);
            }
        } catch (err) {
            if (progressInfo) progressInfo.textContent = '网络错误，请稍后重试';
            setButtonLoading(btn, false);
        }
    }

    /**
     * Connect to SSE status stream for a sync operation
     */
    function connectStatusStream(type) {
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }

        const btn = type === 'users' ? els.syncUsersBtn : els.syncCoursesBtn;
        const progressFill = type === 'users' ? els.usersProgressFill : els.coursesProgressFill;
        const progressInfo = type === 'users' ? els.usersProgressInfo : els.coursesProgressInfo;

        const es = new EventSource('/api/sync/' + type + '/status');
        activeEventSource = es;

        es.onmessage = function(event) {
            let status;
            try {
                status = JSON.parse(event.data);
            } catch (e) {
                return;
            }

            if (progressFill) {
                const pct = status.total > 0
                    ? Math.round((status.progress / status.total) * 100)
                    : 0;
                progressFill.style.width = pct + '%';
                setProgressStriped(progressFill, status.running);
                if (!status.running && status.completed) {
                    progressFill.classList.add('progress-fill-complete');
                    setTimeout(function() {
                        progressFill.classList.remove('progress-fill-complete');
                    }, 2000);
                }
            }

            if (progressInfo) {
                progressInfo.textContent = status.message || '';
            }

            if (!status.running && (status.completed || status.error)) {
                setButtonLoading(btn, false);
                setProgressStriped(progressFill, false);
                if (status.error && progressInfo) {
                    progressInfo.textContent = '错误: ' + status.error;
                } else if (status.completed && progressInfo) {
                    progressInfo.textContent = status.message || '完成';
                }
                es.close();
                activeEventSource = null;
            }
        };

        es.onerror = function() {
            setButtonLoading(btn, false);
            if (progressInfo) progressInfo.textContent = '连接中断';
            es.close();
            activeEventSource = null;
        };
    }

    /**
     * Toggle loading state on a button
     */
    function setButtonLoading(btn, loading) {
        if (!btn) return;
        const text = btn.querySelector('.button-text');
        const loader = btn.querySelector('.button-loader');
        btn.disabled = loading || !authState.is_admin;
        if (text) text.classList.toggle('hidden', loading);
        if (loader) loader.classList.toggle('hidden', !loading);
    }

    /**
     * Check if user prefers reduced motion
     */
    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    /**
     * Animate a number from start to end with counting effect
     */
    function animateNumber(element, endValue, duration) {
        if (!element) return;

        // Respect reduced motion preference
        if (prefersReducedMotion()) {
            element.textContent = String(endValue);
            return { cancel: function() {} };
        }

        duration = duration || 600;
        var startValue = 0;
        var startTime = null;
        var isCounting = true;

        // Try to parse current value as starting point
        var currentText = element.textContent.replace(/,/g, '').trim();
        var parsed = parseInt(currentText, 10);
        if (!isNaN(parsed) && parsed !== endValue) {
            startValue = parsed;
        }

        // If going from non-number (like "—"), add pop animation
        var fromDash = currentText === '—' || currentText === '';
        if (fromDash) {
            element.classList.add('number-animate');
            setTimeout(function() {
                element.classList.remove('number-animate');
            }, duration + 100);
        }

        function step(timestamp) {
            if (!startTime) startTime = timestamp;
            var elapsed = timestamp - startTime;
            var progress = Math.min(elapsed / duration, 1);
            // Ease out cubic
            var eased = 1 - Math.pow(1 - progress, 3);
            var current = Math.round(startValue + (endValue - startValue) * eased);
            element.textContent = String(current);
            if (progress < 1 && isCounting) {
                requestAnimationFrame(step);
            } else {
                element.textContent = String(endValue);
            }
        }
        requestAnimationFrame(step);

        return {
            cancel: function() { isCounting = false; }
        };
    }

    /**
     * Show skeleton loading state on preview stats
     */
    function setPreviewSkeleton(show) {
        if (els.previewCourseCount) {
            els.previewCourseCount.classList.toggle('skeleton', show);
            els.previewCourseCount.classList.toggle('skeleton-text', show);
            if (show) els.previewCourseCount.textContent = '000';
        }
        if (els.previewUserCount) {
            els.previewUserCount.classList.toggle('skeleton', show);
            els.previewUserCount.classList.toggle('skeleton-text', show);
            if (show) els.previewUserCount.textContent = '000';
        }
        if (els.previewLastSync) {
            els.previewLastSync.classList.toggle('skeleton', show);
            els.previewLastSync.classList.toggle('skeleton-text', show);
            if (show) els.previewLastSync.textContent = '0000-00-00';
        }
    }

    /**
     * Show skeleton loading state on history table
     */
    function setHistorySkeleton(show) {
        var tbody = els.historyTableBody;
        if (!tbody) return;
        if (show) {
            tbody.innerHTML = '';
            for (var i = 0; i < 5; i++) {
                var tr = document.createElement('tr');
                tr.innerHTML =
                    '<td><span class="skeleton skeleton-text" style="width:120px">loading</span></td>' +
                    '<td><span class="skeleton skeleton-text" style="width:60px">loading</span></td>' +
                    '<td><span class="skeleton skeleton-text" style="width:160px">loading</span></td>' +
                    '<td><span class="skeleton skeleton-text" style="width:40px">loading</span></td>' +
                    '<td><span class="skeleton skeleton-text" style="width:50px">loading</span></td>' +
                    '<td><span class="skeleton skeleton-text" style="width:100px">loading</span></td>';
                tbody.appendChild(tr);
            }
            if (els.historyTableContainer) els.historyTableContainer.classList.remove('hidden');
            if (els.historyEmptyState) els.historyEmptyState.classList.add('hidden');
            if (els.historyPagination) els.historyPagination.classList.add('hidden');
        }
    }

    /**
     * Set progress bar striped animation state
     */
    function setProgressStriped(fillEl, striped) {
        if (!fillEl) return;
        fillEl.classList.toggle('progress-fill-striped', striped);
    }

    /**
     * Update step indicator with animated line fill and pulse effects
     */
    function updateSteps(step) {
        var steps = [els.step1, els.step2, els.step3, els.step4];
        var lines = document.querySelectorAll('.step-line');

        steps.forEach(function(s, i) {
            if (!s) return;
            var circle = s.querySelector('.step-circle');
            s.classList.remove('done', 'active');
            if (circle) circle.classList.remove('step-circle-pulse');

            if (i + 1 < step) {
                s.classList.add('done');
                // Fill the line before this step
                if (lines[i - 1]) {
                    lines[i - 1].classList.add('step-line-fill');
                    lines[i - 1].style.background = 'var(--success-500)';
                }
            } else if (i + 1 === step) {
                s.classList.add('active');
                if (circle) circle.classList.add('step-circle-pulse');
                // Fill the line before this step too
                if (lines[i - 1]) {
                    lines[i - 1].classList.add('step-line-fill');
                    lines[i - 1].style.background = 'var(--success-500)';
                }
            } else {
                // Reset lines after current step
                if (lines[i - 1]) {
                    lines[i - 1].classList.remove('step-line-fill');
                    lines[i - 1].style.background = '';
                }
            }
        });
    }

    /**
     * Start governance audit (pipeline: users -> courses -> governance)
     */
    async function startGovernance() {
        if (!authState.is_admin) return;
        isGovernanceRunning = true;

        if (els.governanceProgressFill) els.governanceProgressFill.style.width = '0%';
        if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '准备中...';
        if (els.governanceStats) els.governanceStats.classList.add('hidden');
        if (els.governanceResults) els.governanceResults.classList.add('hidden');
        if (els.stepDetails) els.stepDetails.textContent = '';
        currentRunId = '';
        if (els.exportResultsBtn) els.exportResultsBtn.classList.add('hidden');
        openGovernanceProgressModal();

        if (els.liveTotal) els.liveTotal.textContent = '0';
        if (els.liveProgress) els.liveProgress.textContent = '0';
        if (els.liveCompliant) els.liveCompliant.textContent = '0';
        if (els.liveMajor) els.liveMajor.textContent = '0';

        updateSteps(2);
        setGovernanceControlsEnabled(false);

        try {
            var startDate = els.governanceStartDate ? els.governanceStartDate.value : '';
            var endDate = els.governanceEndDate ? els.governanceEndDate.value : '';

            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '步骤 1/3：更新用户列表...';
            if (els.stepDetails) els.stepDetails.textContent = '同步用户列表...';
            await waitForSync('users');

            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '步骤 2/3：更新课程信息...';
            if (els.stepDetails) els.stepDetails.textContent = '同步课程信息...';
            await waitForSync('courses', startDate, endDate);

            updateSteps(3);
            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '步骤 3/3：治理培训数据...';
            if (els.stepDetails) els.stepDetails.textContent = '执行审核...';
            await waitForGovernance(startDate, endDate);

            updateSteps(4);
            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '治理流程完成';
            if (els.stepDetails) els.stepDetails.textContent = '';
        } catch (err) {
            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '流程中断: ' + err.message;
            closeGovernanceProgressModal();
            showToast('治理流程中断：' + err.message, 'error');
        } finally {
            isGovernanceRunning = false;
            setGovernanceControlsEnabled(true);
            loadGovernanceRuns();
        }
    }

    /**
     * Quick governance - skip sync, audit only
     */
    async function quickGovernance() {
        if (!authState.is_admin) return;
        isGovernanceRunning = true;

        if (els.governanceProgressFill) els.governanceProgressFill.style.width = '0%';
        if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '准备中...';
        if (els.governanceStats) els.governanceStats.classList.add('hidden');
        if (els.governanceResults) els.governanceResults.classList.add('hidden');
        if (els.stepDetails) els.stepDetails.textContent = '';
        currentRunId = '';
        if (els.exportResultsBtn) els.exportResultsBtn.classList.add('hidden');
        openGovernanceProgressModal();

        if (els.liveTotal) els.liveTotal.textContent = '0';
        if (els.liveProgress) els.liveProgress.textContent = '0';
        if (els.liveCompliant) els.liveCompliant.textContent = '0';
        if (els.liveMajor) els.liveMajor.textContent = '0';

        updateSteps(3);
        setGovernanceControlsEnabled(false);

        try {
            var startDate = els.governanceStartDate ? els.governanceStartDate.value : '';
            var endDate = els.governanceEndDate ? els.governanceEndDate.value : '';

            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '快速治理：直接执行审核...';
            if (els.stepDetails) els.stepDetails.textContent = '基于本地已有数据执行审核';
            await waitForGovernance(startDate, endDate);

            updateSteps(4);
            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '治理流程完成';
            if (els.stepDetails) els.stepDetails.textContent = '';
        } catch (err) {
            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '流程中断: ' + err.message;
            closeGovernanceProgressModal();
            showToast('治理流程中断：' + err.message, 'error');
        } finally {
            isGovernanceRunning = false;
            setGovernanceControlsEnabled(true);
            loadGovernanceRuns();
        }
    }

    /**
     * Resume a previously interrupted governance run
     */
    async function resumeGovernance() {
        if (!authState.is_admin) return;
        isGovernanceRunning = true;

        var runId = currentRunId;
        if (!runId) {
            showToast('请先选择一条中断的治理记录', 'warning');
            return;
        }

        if (els.governanceProgressFill) els.governanceProgressFill.style.width = '0%';
        if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '准备中...';
        if (els.governanceStats) els.governanceStats.classList.add('hidden');
        if (els.governanceResults) els.governanceResults.classList.add('hidden');
        currentRunId = '';
        if (els.exportResultsBtn) els.exportResultsBtn.classList.add('hidden');
        openGovernanceProgressModal();

        setGovernanceControlsEnabled(false);

        try {
            const response = await fetch('/api/governance/runs/' + runId + '/resume', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await response.json();
            if (data.success) {
                connectGovernanceStream();
            } else {
                if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = data.error || '启动失败';
                isGovernanceRunning = false;
                setGovernanceControlsEnabled(true);
                closeGovernanceProgressModal();
                showToast(data.error || '启动失败', 'error');
            }
        } catch (err) {
            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '网络错误，请稍后重试';
            isGovernanceRunning = false;
            setGovernanceControlsEnabled(true);
            loadGovernanceRuns();
            closeGovernanceProgressModal();
            showToast('网络错误，请稍后重试', 'error');
        }
    }

    /**
     * Connect to SSE stream for governance progress
     */
    function connectGovernanceStream() {
        if (activeEventSource) {
            activeEventSource.close();
            activeEventSource = null;
        }

        const es = new EventSource('/api/governance/status');
        activeEventSource = es;

        es.onmessage = function(event) {
            let status;
            try {
                status = JSON.parse(event.data);
            } catch (e) {
                return;
            }

            if (els.governanceProgressFill) {
                const pct = status.total > 0
                    ? Math.round((status.progress / status.total) * 100)
                    : 0;
                els.governanceProgressFill.style.width = pct + '%';
                setProgressStriped(els.governanceProgressFill, status.running);
                if (!status.running && status.completed) {
                    els.governanceProgressFill.classList.add('progress-fill-complete');
                    setTimeout(function() {
                        els.governanceProgressFill.classList.remove('progress-fill-complete');
                    }, 2000);
                }
            }

            if (els.governanceProgressInfo) {
                els.governanceProgressInfo.textContent = status.message || '';
            }

            if (els.liveTotal) els.liveTotal.textContent = status.total || 0;
            if (els.liveProgress) els.liveProgress.textContent = status.progress || 0;
            if (els.liveCompliant) els.liveCompliant.textContent = status.compliant_count || 0;
            if (els.liveMajor) els.liveMajor.textContent = status.major_count || 0;

            if (!status.running && (status.completed || status.error)) {
                isGovernanceRunning = false;
                setGovernanceControlsEnabled(true);
                setProgressStriped(els.governanceProgressFill, false);
                if (status.error && els.governanceProgressInfo) {
                    els.governanceProgressInfo.textContent = '错误: ' + status.error;
                }
                es.close();
                activeEventSource = null;
                if (status.run_id) {
                    currentRunId = status.run_id;
                    loadGovernanceRuns();
                    if (els.exportResultsBtn) els.exportResultsBtn.classList.remove('hidden');
                    openResultsModal(status.run_id);
                }
                closeGovernanceProgressModal();
                if (status.error) {
                    showToast('治理执行出错：' + status.error, 'error');
                }
            }
        };

        es.onerror = function() {
            isGovernanceRunning = false;
            setGovernanceControlsEnabled(true);
            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '连接中断';
            es.close();
            activeEventSource = null;
            loadGovernanceRuns();
            closeGovernanceProgressModal();
            showToast('SSE 连接中断', 'error');
        };
    }

    /**
     * Wait for a sync operation to complete (Promise-based, for pipeline use).
     */
    function waitForSync(type, startDate, endDate) {
        return new Promise(function(resolve, reject) {
            var progressContainer = type === 'users' ? els.usersProgress : els.coursesProgress;
            var progressFill = type === 'users' ? els.usersProgressFill : els.coursesProgressFill;
            var progressInfo = type === 'users' ? els.usersProgressInfo : els.coursesProgressInfo;

            if (progressFill) progressFill.style.width = '0%';
            if (progressInfo) progressInfo.textContent = '准备中...';
            if (progressContainer) progressContainer.classList.remove('hidden');

            var body = {};
            if (type === 'courses') {
                if (startDate) body.start_date = startDate;
                if (endDate) body.end_date = endDate;
            }

            fetch('/api/sync/' + type + '/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (!data.success) {
                    reject(new Error(data.error || '启动失败'));
                    return;
                }

                var es = new EventSource('/api/sync/' + type + '/status');

                es.onmessage = function(event) {
                    var status;
                    try {
                        status = JSON.parse(event.data);
                    } catch (e) {
                        return;
                    }

                    if (progressFill) {
                        var pct = status.total > 0
                            ? Math.round((status.progress / status.total) * 100)
                            : 0;
                        progressFill.style.width = pct + '%';
                        setProgressStriped(progressFill, status.running);
                        if (!status.running && status.completed) {
                            progressFill.classList.add('progress-fill-complete');
                            setTimeout(function() {
                                progressFill.classList.remove('progress-fill-complete');
                            }, 2000);
                        }
                    }
                    if (progressInfo) {
                        progressInfo.textContent = status.message || '';
                    }

                    if (!status.running && (status.completed || status.error)) {
                        setProgressStriped(progressFill, false);
                        es.close();
                        if (status.error) {
                            reject(new Error(status.error));
                        } else {
                            resolve();
                        }
                    }
                };

                es.onerror = function() {
                    setProgressStriped(progressFill, false);
                    es.close();
                    reject(new Error('连接中断'));
                };
            })
            .catch(function(err) {
                reject(new Error('网络错误，请稍后重试'));
            });
        });
    }

    /**
     * Wait for governance audit to complete (Promise-based, for pipeline use).
     */
    function waitForGovernance(startDate, endDate) {
        return new Promise(function(resolve, reject) {
            if (els.governanceProgressFill) els.governanceProgressFill.style.width = '0%';
            if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = '准备中...';
            if (els.governanceStats) els.governanceStats.classList.add('hidden');
            if (els.governanceResults) els.governanceResults.classList.add('hidden');
            openGovernanceProgressModal();

            if (els.liveTotal) els.liveTotal.textContent = '0';
            if (els.liveProgress) els.liveProgress.textContent = '0';
            if (els.liveCompliant) els.liveCompliant.textContent = '0';
            if (els.liveMajor) els.liveMajor.textContent = '0';

            var body = {};
            if (startDate) body.start_date = startDate;
            if (endDate) body.end_date = endDate;

            fetch('/api/governance/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body),
            })
            .then(function(response) { return response.json(); })
            .then(function(data) {
                if (!data.success) {
                    reject(new Error(data.error || '启动失败'));
                    return;
                }

                var es = new EventSource('/api/governance/status');

                es.onmessage = function(event) {
                    var status;
                    try {
                        status = JSON.parse(event.data);
                    } catch (e) {
                        return;
                    }

                    if (els.governanceProgressFill) {
                        var pct = status.total > 0
                            ? Math.round((status.progress / status.total) * 100)
                            : 0;
                        els.governanceProgressFill.style.width = pct + '%';
                        setProgressStriped(els.governanceProgressFill, status.running);
                        if (!status.running && status.completed) {
                            els.governanceProgressFill.classList.add('progress-fill-complete');
                            setTimeout(function() {
                                els.governanceProgressFill.classList.remove('progress-fill-complete');
                            }, 2000);
                        }
                    }
                    if (els.governanceProgressInfo) {
                        els.governanceProgressInfo.textContent = status.message || '';
                    }

                    if (els.liveTotal) els.liveTotal.textContent = status.total || 0;
                    if (els.liveProgress) els.liveProgress.textContent = status.progress || 0;
                    if (els.liveCompliant) els.liveCompliant.textContent = status.compliant_count || 0;
                    if (els.liveMajor) els.liveMajor.textContent = status.major_count || 0;

                    if (!status.running && (status.completed || status.error)) {
                        setProgressStriped(els.governanceProgressFill, false);
                        es.close();
                        if (status.error) {
                            closeGovernanceProgressModal();
                            reject(new Error(status.error));
                        } else {
                            if (status.run_id) {
                                loadGovernanceRuns();
                                openResultsModal(status.run_id);
                            }
                            closeGovernanceProgressModal();
                            resolve();
                        }
                    }
                };

                es.onerror = function() {
                    setProgressStriped(els.governanceProgressFill, false);
                    es.close();
                    reject(new Error('连接中断'));
                };
            })
            .catch(function(err) {
                reject(new Error('网络错误，请稍后重试'));
            });
        });
    }

    /**
     * Check if there's an active governance run and reconnect SSE.
     */
    async function checkAndConnectActiveGovernance() {
        try {
            const response = await fetch('/api/governance/current');
            const data = await response.json();
            if (data.running && data.run_id) {
                isGovernanceRunning = true;
                if (els.governanceProgressFill) els.governanceProgressFill.style.width = '0%';
                if (els.governanceProgressInfo) els.governanceProgressInfo.textContent = data.message || '恢复连接...';
                if (els.governanceStats) els.governanceStats.classList.add('hidden');
                if (els.governanceResults) els.governanceResults.classList.add('hidden');
                openGovernanceProgressModal();

                if (els.liveTotal) els.liveTotal.textContent = data.total || 0;
                if (els.liveProgress) els.liveProgress.textContent = data.progress || 0;
                if (els.liveCompliant) els.liveCompliant.textContent = '0';
                if (els.liveMajor) els.liveMajor.textContent = '0';

                setGovernanceControlsEnabled(false);
                connectGovernanceStream();
            }
        } catch (err) {
            // ignore
        }
    }

    /**
     * Load historical governance runs into table
     */
    async function loadGovernanceRuns() {
        setHistorySkeleton(true);
        try {
            const response = await fetch('/api/governance/runs');
            const data = await response.json();
            if (!data.success) {
                setHistorySkeleton(false);
                return;
            }

            historyRuns = data.runs || [];
            filterHistory();

            // Auto-select interrupted run if on new tab and none selected
            var interruptedRun = historyRuns.find(function(r) { return r.status === 'interrupted'; });
            if (interruptedRun && !currentRunId) {
                selectGovernanceRun(interruptedRun.run_id, 'interrupted');
            }
        } catch (err) {
            // ignore
        }
    }

    /**
     * Filter and sort history runs
     */
    function filterHistory() {
        var search = els.historySearchInput ? els.historySearchInput.value.toLowerCase() : '';
        var statusFilter = els.historyStatusFilter ? els.historyStatusFilter.value : '';
        var sortBy = els.historySortBy ? els.historySortBy.value : 'started_at_desc';

        historyFiltered = historyRuns.filter(function(run) {
            var matchSearch = true;
            if (search) {
                var range = (run.start_date || '') + ' ~ ' + (run.end_date || '');
                matchSearch = range.toLowerCase().indexOf(search) !== -1;
            }
            var matchStatus = true;
            if (statusFilter) {
                matchStatus = run.status === statusFilter;
            }
            return matchSearch && matchStatus;
        });

        historyFiltered.sort(function(a, b) {
            if (sortBy === 'started_at_desc') {
                return (b.started_at || '').localeCompare(a.started_at || '');
            }
            return (a.started_at || '').localeCompare(b.started_at || '');
        });

        historyPage = 1;
        renderHistoryPage();
    }

    /**
     * Render current page of history table
     */
    function renderHistoryPage() {
        var tbody = els.historyTableBody;
        if (!tbody) return;

        var start = (historyPage - 1) * historyPageSize;
        var end = start + historyPageSize;
        var pageRuns = historyFiltered.slice(start, end);

        tbody.innerHTML = '';

        if (historyFiltered.length === 0) {
            if (els.historyTableContainer) els.historyTableContainer.classList.add('hidden');
            if (els.historyEmptyState) els.historyEmptyState.classList.remove('hidden');
            if (els.historyPagination) els.historyPagination.classList.add('hidden');
            return;
        }

        if (els.historyTableContainer) els.historyTableContainer.classList.remove('hidden');
        if (els.historyEmptyState) els.historyEmptyState.classList.add('hidden');
        if (els.historyPagination) els.historyPagination.classList.remove('hidden');

        var maxPage = Math.ceil(historyFiltered.length / historyPageSize);
        if (els.historyPageInfo) {
            els.historyPageInfo.textContent = '第 ' + historyPage + ' / ' + maxPage + ' 页，共 ' + historyFiltered.length + ' 条';
        }
        if (els.historyPrevPage) els.historyPrevPage.disabled = historyPage <= 1;
        if (els.historyNextPage) els.historyNextPage.disabled = historyPage >= maxPage;

        pageRuns.forEach(function(run) {
            var tr = document.createElement('tr');

            var started = run.started_at ? run.started_at.replace('T', ' ').substring(0, 16) : '';
            var dateRange = run.start_date && run.end_date
                ? run.start_date + ' ~ ' + run.end_date
                : (run.start_date || run.end_date || '—');
            var courseCount = run.total_courses !== undefined ? run.total_courses : '—';
            var compliantRate = run.compliant_rate !== undefined ? run.compliant_rate + '%' : '—';

            var statusClass = 'status-' + (run.status || 'unknown');
            var statusLabel = {
                'completed': '已完成',
                'running': '运行中',
                'interrupted': '已中断',
                'failed': '失败'
            }[run.status] || run.status;

            var isSelected = currentRunId === run.run_id;
            if (isSelected) tr.style.background = 'var(--brand-50)';

            tr.innerHTML =
                '<td>' + escapeHtml(started) + '</td>' +
                '<td><span class="run-item-status ' + statusClass + '">' + escapeHtml(statusLabel) + '</span></td>' +
                '<td>' + escapeHtml(dateRange) + '</td>' +
                '<td>' + escapeHtml(String(courseCount)) + '</td>' +
                '<td>' + escapeHtml(compliantRate) + '</td>' +
                '<td class="history-actions">' +
                    '<button class="history-action-btn view" data-action="view" data-run-id="' + escapeHtml(run.run_id) + '">查看</button>' +
                    (run.status === 'interrupted' ? '<button class="history-action-btn continue" data-action="continue" data-run-id="' + escapeHtml(run.run_id) + '">继续</button>' : '') +
                    '<button class="history-action-btn delete" data-action="delete" data-run-id="' + escapeHtml(run.run_id) + '">删除</button>' +
                '</td>';

            tbody.appendChild(tr);
        });

        // Attach event listeners to action buttons
        tbody.querySelectorAll('.history-action-btn').forEach(function(btn) {
            btn.addEventListener('click', function() {
                var action = btn.dataset.action;
                var runId = btn.dataset.runId;
                if (action === 'view') {
                    var run = historyRuns.find(function(r) { return r.run_id === runId; });
                    selectGovernanceRun(runId, run ? run.status : '');
                    openResultsModal(runId);
                } else if (action === 'continue') {
                    var run = historyRuns.find(function(r) { return r.run_id === runId; });
                    selectGovernanceRun(runId, 'interrupted');
                    resumeGovernance();
                } else if (action === 'delete') {
                    if (confirm('确定要删除这条治理记录吗？')) {
                        var row = btn.closest('tr');
                        if (row) {
                            row.classList.add('history-row-deleting');
                            row.style.background = 'var(--danger-50)';
                        }
                        setTimeout(function() {
                            deleteGovernanceRun(runId);
                        }, 350);
                    }
                }
            });
        });
    }

    /**
     * Select a governance run and update UI
     */
    function selectGovernanceRun(runId, status) {
        selectedRunStatus = status;

        if (!runId) {
            if (els.governanceStats) els.governanceStats.classList.add('hidden');
            if (els.governanceResults) els.governanceResults.classList.add('hidden');
            if (els.exportResultsBtn) els.exportResultsBtn.classList.add('hidden');
            closeGovernanceProgressModal();
            currentRunId = '';
            selectedRunStatus = '';
        }

        if (els.resumeGovernanceBtn) {
            var canResume = runId && status === 'interrupted';
            els.resumeGovernanceBtn.disabled = !canResume || !authState.is_admin;
            els.resumeGovernanceBtn.classList.toggle('hidden', !canResume);
        }

        if (els.startGovernanceBtn) {
            if (runId && status === 'interrupted') {
                els.startGovernanceBtn.disabled = true;
            } else {
                refreshStartGovernanceBtn();
            }
        }

        if (runId && status === 'running') {
            setGovernanceControlsEnabled(false);
            openGovernanceProgressModal();
            connectGovernanceStream();
        }

        // Re-render history to show selection highlight
        renderHistoryPage();
    }

    /**
     * Load and display governance results for a run
     */
    async function loadGovernanceResults(runId) {
        if (!runId) return;
        currentRunId = runId;
        try {
            const response = await fetch('/api/governance/runs/' + runId + '/results');
            if (!response.ok) {
                throw new Error('HTTP ' + response.status);
            }
            const data = await response.json();
            if (!data.success) {
                throw new Error(data.error || '加载失败');
            }

            const stats = data.stats || {};
            var totalVal = stats.total || 0;
            var compliantVal = stats.compliant || 0;
            var majorVal = stats.major || 0;

            if (els.statTotal) animateNumber(els.statTotal, totalVal, 600);
            if (els.statCompliant) setTimeout(function() { animateNumber(els.statCompliant, compliantVal, 600); }, 120);
            if (els.statMajor) setTimeout(function() { animateNumber(els.statMajor, majorVal, 600); }, 240);
            if (els.governanceStats) els.governanceStats.classList.remove('hidden');

            const tbody = els.governanceResultsBody;
            if (!tbody) return;
            tbody.innerHTML = '';

            var filterLevel = els.resultsFilterLevel ? els.resultsFilterLevel.value : 'all';
            var filterRule = els.resultsFilterRule ? els.resultsFilterRule.value : 'all';
            var results = data.results || [];

            if (filterLevel === 'non_compliant') {
                results = results.filter(function(r) { return !r.overall_compliant; });
            }

            if (filterRule !== 'all') {
                var ruleId = parseInt(filterRule, 10);
                results = results.filter(function(r) {
                    var ruleResults = r.rule_results || [];
                    var rule = ruleResults.find(function(rr) { return rr.rule_id === ruleId; });
                    return rule && !rule.compliant;
                });
            }

            results.forEach(function(r) {
                var tr = document.createElement('tr');
                var levelClass = 'badge-' + (r.overall_level || 'unknown');
                var statusText = r.overall_compliant ? '合规' : '不合规';

                tr.innerHTML =
                    '<td>' + escapeHtml(r.course_id || '') + '</td>' +
                    '<td class="course-name-cell" title="' + escapeHtml(r.course_name || '') + '">' + escapeHtml(truncateText(r.course_name, 40)) + '</td>' +
                    '<td class="creator-cell"><div class="creator-name">' + escapeHtml(r.creator_name || '') + '</div><div class="creator-email">' + escapeHtml(r.creator_email || '') + '</div></td>' +
                    '<td><a href="' + escapeHtml(r.umu_link || '') + '" target="_blank" rel="noopener" class="umu-link-icon" title="在 UMU 打开" onclick="event.stopPropagation();"><svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg></a></td>' +
                    '<td class="status-cell"><span class="badge ' + levelClass + '">' + badgeIconSvg(r.overall_level || 'unknown') + escapeHtml(statusText) + '</span></td>' +
                    '<td>' + escapeHtml((r.issues || []).join('; ')) + '</td>';

                tr.addEventListener('click', function() {
                    // Remove highlight from other rows
                    var allRows = tbody.querySelectorAll('tr');
                    allRows.forEach(function(r) { r.classList.remove('results-table-row-highlight'); });
                    // Add highlight to clicked row
                    tr.classList.add('results-table-row-highlight');
                    setTimeout(function() {
                        tr.classList.remove('results-table-row-highlight');
                    }, 600);
                    openCourseDrawer(r);
                });

                tbody.appendChild(tr);
            });

            // Hide table if no rows after filtering; show empty state instead
            if (results.length === 0) {
                if (els.governanceResults) els.governanceResults.classList.add('hidden');
                if (els.exportResultsBtn) els.exportResultsBtn.classList.add('hidden');
            } else {
                if (els.governanceResults) els.governanceResults.classList.remove('hidden');
                if (els.exportResultsBtn) els.exportResultsBtn.classList.remove('hidden');
            }

            // Show "all compliant" state if there are results but none are non-compliant
            if (els.resultsAllCompliantState) {
                if (stats.total > 0 && stats.compliant === stats.total) {
                    els.resultsAllCompliantState.classList.remove('hidden');
                    els.resultsAllCompliantState.classList.add('compliant-celebrate');
                    setTimeout(function() {
                        els.resultsAllCompliantState.classList.remove('compliant-celebrate');
                    }, 600);
                    if (els.governanceResults) els.governanceResults.classList.add('hidden');
                } else {
                    els.resultsAllCompliantState.classList.add('hidden');
                }
            }

            updateResultsEmptyState();
        } catch (err) {
            if (els.governanceResultsBody) els.governanceResultsBody.innerHTML = '';
            if (els.governanceResults) els.governanceResults.classList.add('hidden');
            if (els.exportResultsBtn) els.exportResultsBtn.classList.add('hidden');
        }
    }

    /**
     * Update results empty state visibility
     */
    function updateResultsEmptyState() {
        if (!els.resultsEmptyState) return;
        var hasResults = els.governanceResults && !els.governanceResults.classList.contains('hidden');
        var hasAllCompliant = els.resultsAllCompliantState && !els.resultsAllCompliantState.classList.contains('hidden');
        if (!hasResults && !hasAllCompliant) {
            els.resultsEmptyState.classList.remove('hidden');
        } else {
            els.resultsEmptyState.classList.add('hidden');
        }
    }

    /**
     * Delete a single governance run
     */
    async function deleteGovernanceRun(runId) {
        try {
            const response = await fetch('/api/governance/runs/' + runId, {
                method: 'DELETE',
            });
            const data = await response.json();
            if (data.success) {
                if (currentRunId === runId) {
                    currentRunId = '';
                    selectedRunStatus = '';
                    if (els.governanceStats) els.governanceStats.classList.add('hidden');
                    if (els.governanceResults) els.governanceResults.classList.add('hidden');
                    if (els.exportResultsBtn) els.exportResultsBtn.classList.add('hidden');
                }
                loadGovernanceRuns();
            } else {
                showToast(data.error || '删除失败', 'error');
            }
        } catch (err) {
            showToast('网络错误，请稍后重试', 'error');
        }
    }

    /**
     * Load governance configuration from server
     */
    async function loadGovernanceConfig() {
        if (!authState.is_admin) return;
        try {
            const response = await fetch('/api/governance/config');
            const data = await response.json();
            if (!data.success) return;

            const configs = data.configs || {};
            if (els.forbiddenWords) {
                els.forbiddenWords.value = (configs.forbidden_words || []).join('\n');
            }
            if (els.exceptionWords) {
                els.exceptionWords.value = (configs.exception_words || []).join('\n');
            }
            if (els.fallbackForbiddenWords) {
                els.fallbackForbiddenWords.value = (configs.fallback_forbidden_words || []).join('\n');
            }
            if (els.validCategories) {
                els.validCategories.value = (configs.valid_categories || []).join('\n');
            }
            if (els.evaluationKeywords) {
                els.evaluationKeywords.value = (configs.evaluation_keywords || []).join('\n');
            }
            if (els.meaninglessPlaceholders) {
                els.meaninglessPlaceholders.value = (configs.meaningless_placeholders || []).join('\n');
            }
            if (els.emptyContentMarker) {
                els.emptyContentMarker.value = configs.empty_content_marker || '';
            }
            if (els.excludedUmuId) {
                els.excludedUmuId.value = String(configs.excluded_umu_id || '');
            }
            if (els.excludedLessonType) {
                els.excludedLessonType.value = String(configs.excluded_lesson_type || '');
            }
            if (els.maxDurationHours) {
                els.maxDurationHours.value = String(configs.max_duration_hours || '');
            }
            if (els.excludedCourseIds) {
                els.excludedCourseIds.value = (configs.excluded_course_ids || []).join('\n');
            }
        } catch (err) {
            showConfigMessage('加载配置失败', true);
        }
    }

    /**
     * Save governance configuration to server
     */
    async function saveGovernanceConfig() {
        if (!authState.is_admin) return;

        const configs = [
            { key: 'forbidden_words', value: textToList(els.forbiddenWords) },
            { key: 'exception_words', value: textToList(els.exceptionWords) },
            { key: 'fallback_forbidden_words', value: textToList(els.fallbackForbiddenWords) },
            { key: 'valid_categories', value: textToList(els.validCategories) },
            { key: 'evaluation_keywords', value: textToList(els.evaluationKeywords) },
            { key: 'meaningless_placeholders', value: textToList(els.meaninglessPlaceholders) },
            { key: 'empty_content_marker', value: (els.emptyContentMarker ? els.emptyContentMarker.value.trim() : '') },
            { key: 'excluded_umu_id', value: (els.excludedUmuId ? els.excludedUmuId.value.trim() : '') },
            { key: 'excluded_lesson_type', value: (els.excludedLessonType ? els.excludedLessonType.value.trim() : '') },
            { key: 'max_duration_hours', value: parseInt(els.maxDurationHours ? els.maxDurationHours.value.trim() : '0', 10) || 0 },
            { key: 'excluded_course_ids', value: textToList(els.excludedCourseIds) },
        ];

        setButtonLoading(els.saveConfigBtn, true);
        try {
            const response = await fetch('/api/governance/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ configs: configs }),
            });
            const data = await response.json();
            if (data.success) {
                showConfigMessage('配置已保存', false);
            } else {
                showConfigMessage(data.error || '保存失败', true);
            }
        } catch (err) {
            showConfigMessage('网络错误，请稍后重试', true);
        }
        setButtonLoading(els.saveConfigBtn, false);
    }

    /**
     * Reset governance configuration to defaults
     */
    async function resetGovernanceConfig() {
        if (!authState.is_admin) return;
        if (!confirm('确定要恢复默认配置吗？当前修改将丢失。')) return;
        if (!confirm('此操作不可撤销，确定继续？')) return;

        setButtonLoading(els.resetConfigBtn, true);
        try {
            const response = await fetch('/api/governance/config/reset', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
            });
            const data = await response.json();
            if (data.success) {
                showConfigMessage('已恢复默认配置', false);
                loadGovernanceConfig();
            } else {
                showConfigMessage(data.error || '恢复失败', true);
            }
        } catch (err) {
            showConfigMessage('网络错误，请稍后重试', true);
        }
        setButtonLoading(els.resetConfigBtn, false);
    }

    /**
     * Backup current governance config to a JSON file
     */
    function backupGovernanceConfig() {
        if (!authState.is_admin) return;
        var config = {
            forbidden_words: textToList(els.forbiddenWords),
            exception_words: textToList(els.exceptionWords),
            fallback_forbidden_words: textToList(els.fallbackForbiddenWords),
            valid_categories: textToList(els.validCategories),
            evaluation_keywords: textToList(els.evaluationKeywords),
            meaningless_placeholders: textToList(els.meaninglessPlaceholders),
            empty_content_marker: els.emptyContentMarker ? els.emptyContentMarker.value.trim() : '',
            excluded_umu_id: els.excludedUmuId ? els.excludedUmuId.value.trim() : '',
            excluded_lesson_type: els.excludedLessonType ? els.excludedLessonType.value.trim() : '',
            max_duration_hours: parseInt(els.maxDurationHours ? els.maxDurationHours.value.trim() : '0', 10) || 0,
            excluded_course_ids: textToList(els.excludedCourseIds),
        };
        var blob = new Blob([JSON.stringify(config, null, 2)], { type: 'application/json' });
        var url = URL.createObjectURL(blob);
        var a = document.createElement('a');
        a.href = url;
        var dateStr = new Date().toISOString().slice(0, 10);
        a.download = 'umu-governance-config-' + dateStr + '.json';
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
        showConfigMessage('配置已备份到下载文件夹', false);
    }

    /**
     * Restore governance config from a JSON file
     */
    function restoreGovernanceConfig() {
        if (!authState.is_admin) return;
        var fileInput = els.configFileInput;
        if (!fileInput || !fileInput.files || fileInput.files.length === 0) return;
        var file = fileInput.files[0];
        var reader = new FileReader();
        reader.onload = function(e) {
            try {
                var config = JSON.parse(e.target.result);
                if (els.forbiddenWords) els.forbiddenWords.value = (config.forbidden_words || []).join('\n');
                if (els.exceptionWords) els.exceptionWords.value = (config.exception_words || []).join('\n');
                if (els.fallbackForbiddenWords) els.fallbackForbiddenWords.value = (config.fallback_forbidden_words || []).join('\n');
                if (els.validCategories) els.validCategories.value = (config.valid_categories || []).join('\n');
                if (els.evaluationKeywords) els.evaluationKeywords.value = (config.evaluation_keywords || []).join('\n');
                if (els.meaninglessPlaceholders) els.meaninglessPlaceholders.value = (config.meaningless_placeholders || []).join('\n');
                if (els.emptyContentMarker) els.emptyContentMarker.value = config.empty_content_marker || '';
                if (els.excludedUmuId) els.excludedUmuId.value = String(config.excluded_umu_id || '');
                if (els.excludedLessonType) els.excludedLessonType.value = String(config.excluded_lesson_type || '');
                if (els.maxDurationHours) els.maxDurationHours.value = String(config.max_duration_hours || '0');
                if (els.excludedCourseIds) els.excludedCourseIds.value = (config.excluded_course_ids || []).join('\n');
                showConfigMessage('配置已从文件恢复，请点击「保存配置」以持久化', false);
            } catch (err) {
                showConfigMessage('文件解析失败：' + err.message, true);
            }
            fileInput.value = '';
        };
        reader.onerror = function() {
            showConfigMessage('文件读取失败', true);
            fileInput.value = '';
        };
        reader.readAsText(file);
    }

    /**
     * Convert textarea value to list of non-empty strings
     */
    function textToList(el) {
        if (!el) return [];
        return el.value.split('\n').map(function(s) { return s.trim(); }).filter(function(s) { return s.length > 0; });
    }

    /**
     * Show config page message with slide-in animation
     */
    function showConfigMessage(message, isError) {
        if (!els.configMessage) return;
        els.configMessage.textContent = message;
        els.configMessage.className = 'config-message ' + (isError ? 'error' : 'success') + ' config-message-animated';
        els.configMessage.classList.remove('hidden');
        setTimeout(function() {
            els.configMessage.classList.remove('config-message-animated');
        }, 350);
        setTimeout(function() {
            if (els.configMessage) {
                els.configMessage.classList.add('hidden');
            }
        }, 3000);
    }

    /**
     * Show toast notification with scale animation and progress bar
     */
    function showToast(message, type) {
        type = type || 'info';
        var toast = document.createElement('div');
        toast.className = 'toast toast-' + type;
        toast.textContent = message;

        // Add progress bar
        var progress = document.createElement('div');
        progress.className = 'toast-progress';
        toast.appendChild(progress);

        document.body.appendChild(toast);
        setTimeout(function() {
            toast.classList.add('hiding');
            setTimeout(function() {
                if (toast.parentNode) toast.parentNode.removeChild(toast);
            }, 300);
        }, 3000);
    }

    /**
     * Open course detail drawer
     */
    function openCourseDrawer(course) {
        if (!els.courseDrawer || !els.drawerOverlay) return;

        if (els.drawerTitle) els.drawerTitle.textContent = course.course_name || '课程详情';
        if (els.drawerEditLink) els.drawerEditLink.href = course.umu_link || '#';

        // Basic info
        if (els.drawerBasicInfo) {
            els.drawerBasicInfo.innerHTML =
                '<div class="drawer-info-row"><span class="drawer-info-label">课程ID</span><span class="drawer-info-value">' + escapeHtml(course.course_id || '') + '</span></div>' +
                '<div class="drawer-info-row"><span class="drawer-info-label">创建者</span><span class="drawer-info-value">' + escapeHtml((course.creator_name || '') + (course.creator_email ? ' <' + course.creator_email + '>' : '')) + '</span></div>' +
                '<div class="drawer-info-row"><span class="drawer-info-label">合规状态</span><span class="drawer-info-value">' + (course.overall_compliant ? '✅ 合规' : '❌ 不合规') + '</span></div>' +
                (course.issues && course.issues.length ? '<div class="drawer-info-row"><span class="drawer-info-label">不合规原因</span><span class="drawer-info-value">' + escapeHtml(course.issues.join('；')) + '</span></div>' : '');
        }

        // Rule details
        if (els.drawerRuleDetails) {
            var ruleResults = course.rule_results || [];
            var html = '';
            ruleResults.forEach(function(rule) {
                var isCompliant = rule.compliant;
                var icon = isCompliant ? '✓' : '✕';
                html +=
                    '<div class="drawer-rule-item ' + (isCompliant ? 'compliant' : 'non-compliant') + '">' +
                    '<div class="drawer-rule-icon">' + icon + '</div>' +
                    '<div class="drawer-rule-content">' +
                    '<div class="drawer-rule-name">规则' + rule.rule_id + '：' + escapeHtml(rule.rule_name || '') + '</div>' +
                    (rule.issue ? '<div class="drawer-rule-issue">' + escapeHtml(rule.issue) + '</div>' : '') +
                    '</div>' +
                    '</div>';
            });
            els.drawerRuleDetails.innerHTML = html || '<p style="color:var(--text-secondary);font-size:13px;">无规则审核数据</p>';
        }

        els.drawerOverlay.classList.add('active');
        els.courseDrawer.classList.add('active');
        document.body.style.overflow = 'hidden';

        // Add depth effect to main content
        var mainContent = document.querySelector('.main-content');
        if (mainContent) mainContent.classList.add('drawer-open');

        // Stagger animate drawer content
        setTimeout(function() {
            var drawerSections = els.courseDrawer.querySelectorAll('.drawer-section, .drawer-info-row, .drawer-rule-item');
            drawerSections.forEach(function(el, i) {
                el.classList.add('drawer-stagger-item');
                el.style.animationDelay = (i * 0.05) + 's';
            });
        }, 100);
    }

    /**
     * Close course detail drawer
     */
    function closeDrawer() {
        if (!els.courseDrawer || !els.drawerOverlay) return;
        els.courseDrawer.classList.remove('active');
        els.drawerOverlay.classList.remove('active');
        // Only re-enable body scroll if modal is also closed
        if (!els.resultsModalOverlay || !els.resultsModalOverlay.classList.contains('active')) {
            document.body.style.overflow = '';
        }
        // Remove depth effect from main content
        var mainContent = document.querySelector('.main-content');
        if (mainContent) mainContent.classList.remove('drawer-open');
        // Clean up stagger animation classes
        var drawerSections = els.courseDrawer.querySelectorAll('.drawer-stagger-item');
        drawerSections.forEach(function(el) {
            el.classList.remove('drawer-stagger-item');
            el.style.animationDelay = '';
        });
    }

    /**
     * Debounce utility
     */
    function debounce(fn, delay) {
        var timer;
        return function() {
            var args = arguments;
            clearTimeout(timer);
            timer = setTimeout(function() {
                fn.apply(null, args);
            }, delay);
        };
    }

    /**
     * Truncate text to max length, appending ellipsis if truncated.
     */
    function truncateText(text, maxLen) {
        if (!text) return '';
        if (text.length <= maxLen) return text;
        return text.substring(0, maxLen) + '...';
    }

    /**
     * Escape HTML special characters
     */
    function escapeHtml(text) {
        if (!text) return '';
        return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;');
    }

    // Start
    init();
})();
