// 微信公众号文章智能体 - 前端应用
const { createApp, ref, computed, onMounted, nextTick } = Vue;
const { ElMessage, ElMessageBox } = ElementPlus;

// 自动识别后端地址：如果页面通过后端托管，则使用当前域名；否则回退到 localhost:8001
const API_BASE = (() => {
  const h = window.location.host;
  if (!h || h === '') return 'http://localhost:8001';
  return window.location.protocol + '//' + h;
})();
const WS_BASE = (() => {
  const h = window.location.host;
  if (!h || h === '') return 'ws://localhost:8001';
  return (window.location.protocol === 'https:' ? 'wss:' : 'ws:') + '//' + h;
})();

const app = createApp({
  setup() {
    // ===== 视图状态 =====
    const view = ref('topics');
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
    const previewMode = ref(false);

    // ===== 图片生成 =====
    const generatingImgs = ref(false);
    const regeneratingIdx = ref(-1);
    const imageEngine = ref('seedream');
    const productImageEngine = ref('seedream');
    const imageEngines = ref({});
    const defaultEngine = ref('seedream');

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

    // ===== 产品工坊 =====
    const productView = ref('create');
    const productIdea = ref('');
    const productType = ref('digital_content');
    const productPlatform = ref('xianyu');
    const productGenerating = ref(false);
    const productList = ref([]);
    const currentProduct = ref(null);
    const productFilterType = ref('');
    const productPreviewMode = ref(false);
    const productGenImgs = ref(false);
    const productRegenIdx = ref(-1);
    const productChatMessages = ref([]);
    const productChatInput = ref('');
    const productChatLoading = ref(false);
    const productChatStreaming = ref(false);
    const productChatStreamingText = ref('');
    const productChatBox = ref(null);
    let productWs = null;
    const platformCopyText = ref('');
    const platformCopySuccess = ref(false);

    const productTypes = [
      { value: 'digital_content', label: '数字内容商品', icon: '📖', desc: '电子书/教程/模板/Prompt合集' },
      { value: 'ecommerce_image', label: '电商产品图/详情页', icon: '🛍️', desc: '产品图+详情页文案+卖点' },
      { value: 'virtual_character', label: '虚拟人物/IP形象', icon: '🎭', desc: '角色设定+立绘+表情+场景' },
      { value: 'software_tool', label: '软件/工具类产品', icon: '🔧', desc: '代码/配置+文档+截图' },
    ];

    function productTypeLabel(type) {
      const t = productTypes.find(x => x.value === type);
      return t ? t.label : type;
    }

    const productRenderedContent = computed(() => {
      if (!currentProduct.value || !currentProduct.value.content_md) return '<div class="empty-state">暂无内容</div>';
      let md = currentProduct.value.content_md;
      try { return marked.parse(md); } catch { return md; }
    });

    // ===== 计算属性 =====
    const renderedContent = computed(() => {
      if (!currentArticle.value || !currentArticle.value.content_md) return '<div class="empty-state">暂无内容</div>';
      let md = currentArticle.value.content_md;
      // 去掉开头的 # 标题（标题已在模板中单独显示，避免重复）
      md = md.replace(/^#\s+.+$/m, '').trim();
      // 替换 ![[xxx.png]] 为图片 URL
      md = md.replace(/!\[\[([^\]]+\.(?:png|jpg|jpeg|gif|webp))\]\]/g, (m, f) => `![${f}](${API_BASE}/assets/${f})`);
      // 替换 {{IMG:xxx}} 占位为提示
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
        if (d.message && d.message.includes('已有文章') && !force) {
          generating.value = false;
          loading.value = false;
          try {
            await ElMessageBox.confirm(
              '该选题已有文章，是否重新生成？（重新生成会覆盖现有内容）',
              '提示',
              { confirmButtonText: '重新生成', cancelButtonText: '打开已有', type: 'warning' }
            );
            return await generateArticle(topicId, true);
          } catch {
            await openArticle(d.article_id);
            return;
          }
        }
        ElMessage.success('文章生成完成！');
        await openArticle(d.article_id);
      } catch (e) { ElMessage.error('生成失败：' + e.message); }
      finally { generating.value = false; loading.value = false; }
    }

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

    async function loadImageEngines() {
      try {
        const r = await fetch(`${API_BASE}/api/image_engines/status`);
        const d = await r.json();
        if (r.ok) {
          imageEngines.value = d.engines || {};
          defaultEngine.value = d.default_engine || 'comfyui';
          if (!imageEngine.value) imageEngine.value = defaultEngine.value;
          if (!productImageEngine.value) productImageEngine.value = defaultEngine.value;
        }
      } catch {}
    }

    async function generateAllImages() {
      if (!currentArticle.value) return;
      generatingImgs.value = true;
      const engLabel = imageEngine.value === 'seedream' ? 'Seedream 云生图' : '本地 ComfyUI';
      loadingText.value = `正在使用 ${engLabel} 生成全部图片，请耐心等待...`;
      loading.value = true;
      try {
        const r = await fetch(`${API_BASE}/api/articles/${currentArticle.value.id}/generate_all_images`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ engine: imageEngine.value }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '生成失败');
        await openArticle(currentArticle.value.id);
        const ok = (d.results || []).filter(x => x.status === 'done').length;
        const fail = (d.results || []).filter(x => x.status === 'failed').length;
        ElMessage.success(`[${engLabel}] 图片生成完成：成功 ${ok} 张${fail ? '，失败 ' + fail + ' 张' : ''}`);
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
          body = { prompt: plan.prompt, negative_prompt: plan.negative_prompt, size_preset: plan.size_preset, engine: imageEngine.value };
        } else {
          url = `${API_BASE}/api/images/generate`;
          body = { article_id: currentArticle.value.id, prompt: plan.prompt, negative_prompt: plan.negative_prompt, size_preset: plan.size_preset, index: idx, role: plan.role, section: plan.section, description: plan.description, engine: imageEngine.value };
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
      const wsUrl = `${WS_BASE}/api/articles/${articleId}/chat`;
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

    // ===== 产品工坊方法 =====
    async function generateProduct() {
      if (!productIdea.value.trim()) { ElMessage.warning('请输入产品创意'); return; }
      productGenerating.value = true;
      loadingText.value = '正在生成产品（内容 → 图片规划 → 平台文案）...';
      loading.value = true;
      try {
        const r = await fetch(`${API_BASE}/api/products/generate`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ idea: productIdea.value, product_type: productType.value, platform: productPlatform.value }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '生成失败');
        ElMessage.success('产品生成完成！');
        productIdea.value = '';
        await openProduct(d.product_id);
      } catch (e) { ElMessage.error('生成失败：' + e.message); }
      finally { productGenerating.value = false; loading.value = false; }
    }

    async function loadProducts() {
      try {
        let url = `${API_BASE}/api/products`;
        if (productFilterType.value) url += `?product_type=${productFilterType.value}`;
        const r = await fetch(url);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || `HTTP ${r.status}`);
        productList.value = d.products || [];
      } catch (e) { ElMessage.error('加载产品列表失败：' + errMsg(e)); }
    }

    async function openProduct(id) {
      loading.value = true;
      loadingText.value = '加载产品...';
      try {
        const r = await fetch(`${API_BASE}/api/products/${id}`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '加载失败');
        currentProduct.value = d;
        productChatMessages.value = [];
        productView.value = 'workspace';
        connectProductChat(id);
      } catch (e) { ElMessage.error('加载产品失败：' + e.message); }
      finally { loading.value = false; }
    }

    async function saveProduct() {
      if (!currentProduct.value) return;
      try {
        const r = await fetch(`${API_BASE}/api/products/${currentProduct.value.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ content_md: currentProduct.value.content_md, title: currentProduct.value.title }),
        });
        if (!r.ok) throw new Error('保存失败');
        ElMessage.success('已保存');
      } catch (e) { ElMessage.error('保存失败：' + e.message); }
    }

    async function deleteProduct(id) {
      try {
        await ElMessageBox.confirm('确定删除该产品？删除后不可恢复。', '提示', { confirmButtonText: '删除', cancelButtonText: '取消', type: 'warning' });
        const r = await fetch(`${API_BASE}/api/products/${id}`, { method: 'DELETE' });
        if (!r.ok) throw new Error('删除失败');
        ElMessage.success('已删除');
        loadProducts();
      } catch (e) { if (e !== 'cancel') ElMessage.error('删除失败：' + e.message); }
    }

    function getProductImageByIndex(idx) {
      if (!currentProduct.value || !currentProduct.value.images) return null;
      return currentProduct.value.images.find(i => i.index === idx) || null;
    }
    function getProductImageUrl(idx) {
      const img = getProductImageByIndex(idx);
      return img && img.file_path ? `${API_BASE}/product-assets/${img.file_path}` : '';
    }

    async function generateAllProductImages() {
      if (!currentProduct.value) return;
      productGenImgs.value = true;
      const engLabel = productImageEngine.value === 'seedream' ? 'Seedream 云生图' : '本地 ComfyUI';
      loadingText.value = `正在使用 ${engLabel} 生成全部产品图片，请耐心等待...`;
      loading.value = true;
      try {
        const r = await fetch(`${API_BASE}/api/products/${currentProduct.value.id}/generate_all_images`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ engine: productImageEngine.value }),
        });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '生成失败');
        await openProduct(currentProduct.value.id);
        const ok = (d.results || []).filter(x => x.status === 'done').length;
        const fail = (d.results || []).filter(x => x.status === 'failed').length;
        ElMessage.success(`[${engLabel}] 图片生成完成：成功 ${ok} 张${fail ? '，失败 ' + fail + ' 张' : ''}`);
      } catch (e) { ElMessage.error('图片生成失败：' + e.message); }
      finally { productGenImgs.value = false; loading.value = false; }
    }

    async function regenerateProductImage(idx) {
      if (!currentProduct.value) return;
      const plan = currentProduct.value.image_plan[idx];
      const img = getProductImageByIndex(idx);
      productRegenIdx.value = idx;
      try {
        let url, body;
        if (img && img.id) {
          url = `${API_BASE}/api/products/images/${img.id}/regenerate`;
          body = { prompt: plan.prompt, negative_prompt: plan.negative_prompt, size_preset: plan.size_preset, engine: productImageEngine.value };
        } else {
          url = `${API_BASE}/api/products/images/generate`;
          body = { product_id: currentProduct.value.id, prompt: plan.prompt, negative_prompt: plan.negative_prompt, size_preset: plan.size_preset, index: idx, role: plan.role, section: plan.section, description: plan.description, engine: productImageEngine.value };
        }
        const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '生成失败');
        ElMessage.success('图片已重新生成');
        await openProduct(currentProduct.value.id);
      } catch (e) { ElMessage.error('重新生成失败：' + e.message); }
      finally { productRegenIdx.value = -1; }
    }

    function connectProductChat(productId) {
      if (productWs) { try { productWs.close(); } catch {} }
      const wsUrl = `${WS_BASE}/api/products/${productId}/chat`;
      productWs = new WebSocket(wsUrl);
      productWs.onmessage = (ev) => {
        try {
          const d = JSON.parse(ev.data);
          if (d.type === 'start') { productChatStreaming.value = true; productChatStreamingText.value = ''; }
          else if (d.type === 'chunk') { productChatStreamingText.value += d.content; scrollProductChat(); }
          else if (d.type === 'done') {
            productChatStreaming.value = false;
            productChatMessages.value.push({ role: 'assistant', content: productChatStreamingText.value });
            productChatStreamingText.value = '';
            openProduct(productId);
          }
          else if (d.type === 'error') { productChatStreaming.value = false; ElMessage.error(d.message); }
        } catch {}
      };
    }

    async function sendProductChat() {
      if (!productChatInput.value.trim() || !currentProduct.value) return;
      const msg = productChatInput.value.trim();
      productChatMessages.value.push({ role: 'user', content: msg });
      productChatInput.value = '';
      productChatLoading.value = true;
      try {
        if (productWs && productWs.readyState === WebSocket.OPEN) {
          productWs.send(JSON.stringify({ message: msg }));
        } else {
          ElMessage.warning('对话连接已断开，正在重连...');
          connectProductChat(currentProduct.value.id);
          setTimeout(() => { if (productWs && productWs.readyState === WebSocket.OPEN) productWs.send(JSON.stringify({ message: msg })); }, 1000);
        }
      } catch (e) { ElMessage.error('发送失败：' + e.message); }
      finally { productChatLoading.value = false; }
    }

    function scrollProductChat() {
      nextTick(() => { if (productChatBox.value) productChatBox.value.scrollTop = productChatBox.value.scrollHeight; });
    }

    async function loadPlatformCopy() {
      if (!currentProduct.value) return;
      loading.value = true;
      loadingText.value = '加载平台文案...';
      try {
        const r = await fetch(`${API_BASE}/api/products/${currentProduct.value.id}/platform_copy`);
        const d = await r.json();
        if (!r.ok) throw new Error(d.detail || '加载失败');
        platformCopyText.value = d.formatted_text;
        platformCopySuccess.value = false;
        productView.value = 'platformCopy';
      } catch (e) { ElMessage.error('加载文案失败：' + e.message); }
      finally { loading.value = false; }
    }

    async function copyPlatformCopy() {
      try {
        await navigator.clipboard.writeText(platformCopyText.value);
        platformCopySuccess.value = true;
        ElMessage.success('已复制到剪贴板！');
      } catch (e) {
        const ta = document.createElement('textarea');
        ta.value = platformCopyText.value;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand('copy');
        document.body.removeChild(ta);
        platformCopySuccess.value = true;
        ElMessage.success('已复制到剪贴板！');
      }
    }

    // ===== 导航 =====
    function goTopics() { view.value = 'topics'; loadDates(); }
    function goArticles() { view.value = 'articles'; loadArticles(); }
    function goProducts() { view.value = 'products'; loadProducts(); }

    onMounted(() => { loadDates(); loadArticles(); loadImageEngines(); });

    return {
      view, loading, loadingText,
      dates, selectedDate, topics, selectedTopicId, generating,
      articleList, currentArticle, lastArticle,
      previewMode,
      generatingImgs, regeneratingIdx,
      imageEngine, productImageEngine, imageEngines, defaultEngine, loadImageEngines,
      chatMessages, chatInput, chatLoading, chatStreaming, chatStreamingText, chatBox,
      publishHtml, copySuccess,
      renderedContent,
      loadDates, loadTopics, onSelectDate, generateArticle,
      loadArticles, openArticle, saveArticle,
      getImageByIndex, getImageUrl, generateAllImages, regenerateImage,
      sendChat, goPublish, copyRichText, downloadAllImages,
      goTopics, goArticles,
      productView, productIdea, productType, productPlatform, productGenerating,
      productList, currentProduct, productFilterType, productPreviewMode,
      productGenImgs, productRegenIdx,
      productChatMessages, productChatInput, productChatLoading, productChatStreaming, productChatStreamingText, productChatBox,
      platformCopyText, platformCopySuccess,
      productTypes, productTypeLabel, productRenderedContent,
      generateProduct, loadProducts, openProduct, saveProduct, deleteProduct,
      getProductImageByIndex, getProductImageUrl, generateAllProductImages, regenerateProductImage,
      sendProductChat, loadPlatformCopy, copyPlatformCopy,
      goProducts,
    };
  }
});

app.use(ElementPlus);
for (const [key, comp] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, comp);
}
app.mount('#app');
