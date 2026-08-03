// 微信公众号文章智能体 - 前端应用
const { createApp, ref, computed, onMounted, nextTick } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

const API_BASE = 'http://localhost:8001';

const app = createApp({
  setup() {
    // ===== 视图状态 =====
    const view = ref('topics');  // topics | articles | workspace | publish
    const loading = ref(false);
    const loadingText = ref('');

    // ===== 选题库 =====
    const dates = ref([]);
    const selectedDate = ref('');
    const topics = ref([]);
    const selectedTopicId = ref('');
    const generating = ref(false);

    // ===== 文章 =====
    const articleList = ref([]);
    const currentArticle = ref(null);
    const lastArticle = ref(null);

    // ===== 编辑模式 =====
    const previewMode = ref(false);  // false=编辑 true=预览

    // ===== 图片生成 =====
    const generatingImgs = ref(false);
    const regeneratingIdx = ref(-1);

    // ===== 对话 =====
    const chatMessages = ref([]);
    const chatInput = ref('');
    const chatLoading = ref(false);
    const chatStreaming = ref(false);
    const chatStreamingText = ref('');
    const chatBox = ref(null);
    let ws = null;

    // ===== 发布 =====
    const publishHtml = ref('');
    const copySuccess = ref(false);

    // ===== 计算属性 =====
    const renderedContent = computed(() => {
      if (!currentArticle.value || !currentArticle.value.content_md) return '<div class="empty-state">暂无内容</div>';
      let md = currentArticle.value.content_md;
      // 去掉开头的 # 标题（标题已在模板中单独显示，避免重复）
      md = md.replace(/^#\s+.+$/m, '').trim();
      // 替换 ![[xxx.png]] 为图片 URL
      md = md.replace(/!\[\[([^\]]+\.(?:png|jpg|jpeg|gif|webp))\]\]/g, (m, f) => `![${f}](${API_BASE}/assets/${f})`);
      // 替换 {{IMG:xxx}} 占位为提示（不替换为实际图片，右侧面板可查看图片）
      md = md.replace(/!\[\{\{IMG:(cover|inline-\d+)\}\}\]/g, (m, n) => `> 🖼️ [图片占位：${n}，待生成]`);
      try { return marked.parse(md); } catch { return md; }
    });

    // ===== 选题库 =====
    async function loadDates() {
      try {
        const r = await fetch(`${API_BASE}/api/topics/dates`);
        const d = await r.json();
        dates.value = d.dates || [];
        if (dates.value.length > 0 && !selectedDate.value) {
          selectedDate.value = dates.value[0];
          await loadTopics();
        }
      } catch (e) { ElMessage.error('加载日期失败：' + e.message); }
    }

    async function loadTopics() {
      if (!selectedDate.value) return;
      loading.value = true;
      try {
        const r = await fetch(`${API_BASE}/api/topics?date=${selectedDate.value}`);
        const d = await r.json();
        topics.value = d.topics || [];
      } catch (e) { ElMessage.error('加载选题失败：' + e.message); }
      finally { loading.value = false; }
    }

    function onSelectDate(d) {
      selectedDate.value = d;
      loadTopics();
    }

    async function generateArticle(topicId, force = false) {
      generating.value = true;
      loadingText.value = '正在生成文章（初稿 → 去AI味 → 图片规划）...';
      loading.value = true;
      try {
        const r = await fetch(`${API_BASE}/api/articles/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ topic_id: topicId, force }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '生成失败');
        // 已有文章且未强制重新生成：询问用户
        if (d.message && d.message.includes('已有文章') && !force) {
          generating.value = false;
          loading.value = false;
          try {
            await ElMessageBox.confirm(
              '该选题已有文章，是否重新生成？（重新生成会覆盖现有内容）',
              '提示',
              { confirmButtonText: '重新生成', cancelButtonText: '打开已有', type: 'warning' }
            );
            // 用户选择重新生成
            return await generateArticle(topicId, true);
          } catch {
            // 用户选择打开已有
            await openArticle(d.article_id);
            return;
          }
        }
        ElMessage.success('文章生成完成！');
        await openArticle(d.article_id);
      } catch (e) { ElMessage.error('生成失败：' + e.message); }
      finally { generating.value = false; loading.value = false; }
    }

    // ===== 错误信息格式化 =====
    function errMsg(e) {
      if (!e) return '未知错误';
      if (typeof e === 'string') return e;
      if (e.message && typeof e.message === 'string') return e.message;
      try { return JSON.stringify(e); } catch { return String(e); }
    }

    // ===== 文章列表 =====
    async function loadArticles() {
      try {
        const r = await fetch(`${API_BASE}/api/articles`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        articleList.value = d.articles || [];
      } catch (e) { ElMessage.error('加载文章列表失败：' + errMsg(e)); }
    }

    async function openArticle(id) {
      loading.value = true;
      loadingText.value = '加载文章...';
      try {
        const r = await fetch(`${API_BASE}/api/articles/${id}`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '加载失败');
        currentArticle.value = d;
        lastArticle.value = d;
        view.value = 'workspace';
        connectChat(id);
      } catch (e) { ElMessage.error('加载文章失败：' + e.message); }
      finally { loading.value = false; }
    }

    async function saveArticle() {
      if (!currentArticle.value) return;
      try {
        const r = await fetch(`${API_BASE}/api/articles/${currentArticle.value.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content_md: currentArticle.value.content_md, title: currentArticle.value.title }),
        });
        if (!r.ok) throw new Error('保存失败');
        ElMessage.success('已保存');
      } catch (e) { ElMessage.error('保存失败：' + e.message); }
    }

    // ===== 图片生成 =====
    function getImageByIndex(idx) {
      if (!currentArticle.value || !currentArticle.value.images) return null;
      return currentArticle.value.images.find(i => i.index === idx) || null;
    }
    function getImageUrl(idx) {
      const img = getImageByIndex(idx);
      return img && img.file_path ? `${API_BASE}/assets/${img.file_path}` : '';
    }

    async function generateAllImages() {
      if (!currentArticle.value) return;
      generatingImgs.value = true;
      loadingText.value = '正在生成全部图片，请耐心等待（每张约 10-30 秒）...';
      loading.value = true;
      try {
        const r = await fetch(`${API_BASE}/api/articles/${currentArticle.value.id}/generate_all_images`, { method: 'POST' });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '生成失败');
        // 刷新文章
        await openArticle(currentArticle.value.id);
        const ok = (d.results || []).filter(x => x.status === 'done').length;
        const fail = (d.results || []).filter(x => x.status === 'failed').length;
        ElMessage.success(`图片生成完成：成功 ${ok} 张${fail ? '，失败 ' + fail + ' 张' : ''}`);
      } catch (e) { ElMessage.error('图片生成失败：' + e.message); }
      finally { generatingImgs.value = false; loading.value = false; }
    }

    async function regenerateImage(idx) {
      if (!currentArticle.value) return;
      const plan = currentArticle.value.image_plan[idx];
      const img = getImageByIndex(idx);
      regeneratingIdx.value = idx;
      try {
        let url, body;
        if (img && img.id) {
          url = `${API_BASE}/api/images/${img.id}/regenerate`;
          body = { prompt: plan.prompt, negative_prompt: plan.negative_prompt, size_preset: plan.size_preset };
        } else {
          url = `${API_BASE}/api/images/generate`;
          body = { article_id: currentArticle.value.id, prompt: plan.prompt, negative_prompt: plan.negative_prompt, size_preset: plan.size_preset, index: idx, role: plan.role, section: plan.section, description: plan.description };
        }
        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '生成失败');
        ElMessage.success('图片已重新生成');
        await openArticle(currentArticle.value.id);
      } catch (e) { ElMessage.error('重新生成失败：' + e.message); }
      finally { regeneratingIdx.value = -1; }
    }

    // ===== 对话 =====
    function connectChat(articleId) {
      if (ws) { try { ws.close(); } catch {} }
      const wsUrl = `ws://localhost:8001/api/articles/${articleId}/chat`;
      ws = new WebSocket(wsUrl);
      ws.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data);
          if (d.type === 'start') { chatStreaming.value = true; chatStreamingText.value = ''; }
          else if (d.type === 'chunk') { chatStreamingText.value += d.content; scrollChat(); }
          else if (d.type === 'done') {
            chatStreaming.value = false;
            chatMessages.value.push({ role: 'assistant', content: chatStreamingText.value });
            chatStreamingText.value = '';
            // 刷新文章内容
            openArticle(articleId);
          }
          else if (d.type === 'error') { chatStreaming.value = false; ElMessage.error(d.message); }
        } catch {}
      };
    }

    async function sendChat() {
      if (!chatInput.value.trim() || !currentArticle.value) return;
      const msg = chatInput.value.trim();
      chatMessages.value.push({ role: 'user', content: msg });
      chatInput.value = '';
      chatLoading.value = true;
      try {
        if (ws && ws.readyState === WebSocket.OPEN) {
          ws.send(JSON.stringify({ message: msg }));
        } else {
          ElMessage.warning('对话连接已断开，正在重连...');
          connectChat(currentArticle.value.id);
          setTimeout(() => { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify({ message: msg })); }, 1000);
        }
      } catch (e) { ElMessage.error('发送失败：' + e.message); }
      finally { chatLoading.value = false; }
    }

    function scrollChat() {
      nextTick(() => { if (chatBox.value) chatBox.value.scrollTop = chatBox.value.scrollHeight; });
    }

    // ===== 发布 =====
    async function goPublish() {
      if (!currentArticle.value) return;
      lastArticle.value = currentArticle.value;
      loading.value = true;
      loadingText.value = '生成公众号富文本...';
      try {
        const r = await fetch(`${API_BASE}/api/publish/richtext`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ article_id: currentArticle.value.id }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '生成失败');
        publishHtml.value = d.html;
        copySuccess.value = false;
        view.value = 'publish';
      } catch (e) { ElMessage.error('生成富文本失败：' + e.message); }
      finally { loading.value = false; }
    }

    async function copyRichText() {
      // 选中 .publish-preview 区域并复制
      const range = document.createRange();
      const node = document.querySelector('.publish-preview');
      range.selectNodeContents(node);
      const sel = window.getSelection();
      sel.removeAllRanges();
      sel.addRange(range);
      try {
        document.execCommand('copy');
        copySuccess.value = true;
        ElMessage.success('已复制富文本到剪贴板！');
        sel.removeAllRanges();
      } catch (e) {
        ElMessage.error('复制失败：' + e.message);
      }
    }

    async function downloadAllImages() {
      if (!currentArticle.value || !currentArticle.value.images) return;
      const imgs = currentArticle.value.images.filter(i => i.file_path);
      for (const img of imgs) {
        const a = document.createElement('a');
        a.href = `${API_BASE}/assets/${img.file_path}`;
        a.download = img.file_path;
        a.click();
        await new Promise(r => setTimeout(r, 300));
      }
      ElMessage.success(`已下载 ${imgs.length} 张图片`);
    }

    // ===== 导航 =====
    function goTopics() { view.value = 'topics'; loadDates(); }
    function goArticles() { view.value = 'articles'; loadArticles(); }

    onMounted(() => { loadDates(); loadArticles(); });

    return {
      view, loading, loadingText,
      dates, selectedDate, topics, selectedTopicId, generating,
      articleList, currentArticle, lastArticle,
      previewMode,
      generatingImgs, regeneratingIdx,
      chatMessages, chatInput, chatLoading, chatStreaming, chatStreamingText, chatBox,
      publishHtml, copySuccess,
      renderedContent,
      loadDates, loadTopics, onSelectDate, generateArticle,
      loadArticles, openArticle, saveArticle,
      getImageByIndex, getImageUrl, generateAllImages, regenerateImage,
      sendChat, goPublish, copyRichText, downloadAllImages,
      goTopics, goArticles,
    };
  }
});

app.use(ElementPlus);
for (const [key, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, comp);
}
app.mount('#app');
