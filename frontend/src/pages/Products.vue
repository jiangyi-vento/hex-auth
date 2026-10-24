<template>
  <div class="products-page">
    <div class="page-header">
      <button class="add-btn" @click="showCreateModal = true">
        <Icon :icon="icons.add" />
        添加产品
      </button>
    </div>

    <!-- 搜索和筛选栏 -->
    <div class="toolbar">
      <div class="search-box">
        <Icon :icon="icons.search" class="search-icon" />
        <input
          v-model="searchText"
          type="text"
          placeholder="搜索产品名称或代码"
          @input="handleSearch"
        />
      </div>

      <select v-model="statusFilter" class="filter-select" @change="handleFilter">
        <option value="">全部状态</option>
        <option value="enabled">启用</option>
        <option value="disabled">禁用</option>
      </select>

      <button class="refresh-btn" @click="fetchProducts" :disabled="isLoading">
        <Icon :icon="icons.refresh" />
      </button>
    </div>

    <!-- 表格 -->
    <div class="products-table-wrapper">
      <!-- 骨架屏 -->
      <TableSkeleton v-if="isLoading && products.length === 0" :columns="6" :rows="5" />

      <!-- 空状态 -->
      <div v-else-if="filteredProducts.length === 0" class="empty-state">
        <Icon :icon="icons.info" class="empty-icon" />
        <p>{{ searchText || statusFilter ? '未找到匹配的产品' : '暂无产品数据' }}</p>
        <button v-if="!searchText && !statusFilter" class="empty-action" @click="showCreateModal = true">
          创建第一个产品
        </button>
      </div>

      <!-- 数据表格 -->
      <table v-else class="products-table">
        <thead>
          <tr>
            <th>产品代码</th>
            <th>产品名称</th>
            <th>心跳间隔</th>
            <th>状态</th>
            <th>创建时间</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="product in paginatedProducts" :key="product.id">
            <td><code>{{ product.product_code }}</code></td>
            <td>{{ product.name }}</td>
            <td>{{ product.heartbeat_interval }}秒</td>
            <td>
              <span class="status-badge" :class="product.status">
                {{ product.status === 'enabled' ? '启用' : '禁用' }}
              </span>
            </td>
            <td>{{ formatDate(product.created_at) }}</td>
            <td class="action-buttons">
              <button class="key-btn" @click="openPubKeyModal(product)">
                <Icon :icon="icons.licenses" />
                公钥
              </button>
              <button class="edit-btn" @click="openEditModal(product)">
                <Icon :icon="icons.edit" />
                编辑
              </button>
              <button class="delete-btn" @click="confirmDelete(product)" :disabled="isLoading">
                <Icon :icon="icons.delete" />
                删除
              </button>
            </td>
          </tr>
        </tbody>
      </table>

      <!-- 分页 -->
      <div v-if="filteredProducts.length > pageSize" class="pagination">
        <div class="pagination-info">
          显示 {{ (currentPage - 1) * pageSize + 1 }}-{{ Math.min(currentPage * pageSize, filteredProducts.length) }}
          / 共 {{ filteredProducts.length }} 条
        </div>
        <div class="pagination-controls">
          <button
            class="page-btn"
            :disabled="currentPage === 1"
            @click="currentPage--"
          >
            上一页
          </button>
          <span class="page-numbers">
            <button
              v-for="page in visiblePages"
              :key="page"
              class="page-number"
              :class="{ active: page === currentPage }"
              @click="currentPage = page"
            >
              {{ page }}
            </button>
          </span>
          <button
            class="page-btn"
            :disabled="currentPage === totalPages"
            @click="currentPage++"
          >
            下一页
          </button>
        </div>
      </div>
    </div>

    <!-- 创建产品模态框 -->
    <div v-if="showCreateModal" class="modal-overlay" @click="showCreateModal = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>创建产品</h3>
          <button class="close-btn" @click="showCreateModal = false">×</button>
        </div>
        <form class="modal-form" @submit.prevent="createProduct">
          <div class="form-group">
            <label for="create-product-code">产品代码</label>
            <input
              type="text"
              id="create-product-code"
              v-model="createForm.product_code"
              placeholder="请输入产品代码"
              required
            >
          </div>
          <div class="form-group">
            <label for="create-name">产品名称</label>
            <input
              type="text"
              id="create-name"
              v-model="createForm.name"
              placeholder="请输入产品名称"
              required
            >
          </div>
          <div class="form-group">
            <label for="create-heartbeat-interval">心跳间隔（秒）</label>
            <input
              type="number"
              id="create-heartbeat-interval"
              v-model="createForm.heartbeat_interval"
              placeholder="请输入心跳间隔"
              min="60"
              max="86400"
              required
            >
          </div>
          <div class="form-actions">
            <button type="button" class="cancel-btn" @click="showCreateModal = false">取消</button>
            <button type="submit" class="confirm-btn" :disabled="isLoading">
              {{ isLoading ? '创建中...' : '创建' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- 编辑产品模态框 -->
    <div v-if="showEditModal" class="modal-overlay" @click="showEditModal = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>编辑产品</h3>
          <button class="close-btn" @click="showEditModal = false">×</button>
        </div>
        <form class="modal-form" @submit.prevent="updateProduct">
          <div class="form-group">
            <label for="edit-name">产品名称</label>
            <input
              type="text"
              id="edit-name"
              v-model="editForm.name"
              placeholder="请输入产品名称"
              required
            >
          </div>
          <div class="form-group">
            <label for="edit-heartbeat-interval">心跳间隔（秒）</label>
            <input
              type="number"
              id="edit-heartbeat-interval"
              v-model="editForm.heartbeat_interval"
              placeholder="请输入心跳间隔"
              min="60"
              max="86400"
              required
            >
          </div>
          <div class="form-group">
            <label for="edit-status">状态</label>
            <select id="edit-status" v-model="editForm.status" required>
              <option value="enabled">启用</option>
              <option value="disabled">禁用</option>
            </select>
          </div>
          <div class="form-actions">
            <button type="button" class="cancel-btn" @click="showEditModal = false">取消</button>
            <button type="submit" class="confirm-btn" :disabled="isLoading">
              {{ isLoading ? '更新中...' : '更新' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- 公钥查看模态框 -->
    <div v-if="showPubKeyModal" class="modal-overlay" @click="showPubKeyModal = false">
      <div class="modal" @click.stop>
        <div class="modal-header">
          <h3>产品公钥</h3>
          <button class="close-btn" @click="showPubKeyModal = false">×</button>
        </div>
        <div class="pubkey-body">
          <p class="pubkey-meta">
            {{ pubKeyProduct?.product_code }} · 随客户端分发，用于令牌离线验签（见 API_授权.md 3.4）
          </p>
          <pre class="pubkey-pre">{{ pubKeyProduct?.public_key }}</pre>
          <div class="form-actions">
            <button type="button" class="cancel-btn" @click="showPubKeyModal = false">关闭</button>
            <button type="button" class="confirm-btn" @click="copyPublicKey">复制公钥</button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Icon } from '@iconify/vue'
import icons from '@/icons'
import { Message, Dialog } from '@/utils/message'
import api from '@/api'
import TableSkeleton from '@/components/TableSkeleton.vue'

// 产品列表
const products = ref<any[]>([])

// 加载状态
const isLoading = ref(false)

// 创建模态框状态
const showCreateModal = ref(false)

// 编辑模态框状态
const showEditModal = ref(false)

// 公钥查看模态框状态
const showPubKeyModal = ref(false)
const pubKeyProduct = ref<any>(null)

const openPubKeyModal = (product: any) => {
  pubKeyProduct.value = product
  showPubKeyModal.value = true
}

const copyPublicKey = async () => {
  if (!pubKeyProduct.value) return
  const text = pubKeyProduct.value.public_key
  try {
    await navigator.clipboard.writeText(text)
    Message.success('公钥已复制到剪贴板')
  } catch {
    // 非安全上下文或权限被拒时的兜底方案
    const ta = document.createElement('textarea')
    ta.value = text
    document.body.appendChild(ta)
    ta.select()
    document.execCommand('copy')
    document.body.removeChild(ta)
    Message.success('公钥已复制到剪贴板')
  }
}

// 搜索和筛选
const searchText = ref('')
const statusFilter = ref('')

// 分页
const currentPage = ref(1)
const pageSize = ref(10)

// 创建表单数据
const createForm = ref({
  product_code: '',
  name: '',
  heartbeat_interval: 3600
})

// 编辑表单数据
const editForm = ref({
  id: 0,
  name: '',
  heartbeat_interval: 3600,
  status: 'enabled'
})

// 格式化日期
const formatDate = (dateString: string) => {
  const date = new Date(dateString)
  return date.toLocaleString()
}

// 过滤后的产品
const filteredProducts = computed(() => {
  let result = products.value

  // 搜索过滤
  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    result = result.filter(p =>
      p.name.toLowerCase().includes(search) ||
      p.product_code.toLowerCase().includes(search)
    )
  }

  // 状态过滤
  if (statusFilter.value) {
    result = result.filter(p => p.status === statusFilter.value)
  }

  return result
})

// 总页数
const totalPages = computed(() => Math.ceil(filteredProducts.value.length / pageSize.value))

// 可见页码
const visiblePages = computed(() => {
  const pages: number[] = []
  const maxVisible = 5
  let start = Math.max(1, currentPage.value - Math.floor(maxVisible / 2))
  let end = Math.min(totalPages.value, start + maxVisible - 1)

  if (end - start < maxVisible - 1) {
    start = Math.max(1, end - maxVisible + 1)
  }

  for (let i = start; i <= end; i++) {
    pages.push(i)
  }

  return pages
})

// 当前页的产品
const paginatedProducts = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredProducts.value.slice(start, end)
})

// 搜索处理
const handleSearch = () => {
  currentPage.value = 1
}

// 筛选处理
const handleFilter = () => {
  currentPage.value = 1
}

// 获取产品列表
const fetchProducts = async () => {
  isLoading.value = true
  try {
    const response = await api.get('/admin/product/')
    products.value = response
  } catch (error) {
    Message.error('获取产品列表失败')
  } finally {
    isLoading.value = false
  }
}

// 创建产品
const createProduct = async () => {
  isLoading.value = true
  try {
    // 确保数据类型正确
    const payload = {
      product_code: createForm.value.product_code.trim(),
      name: createForm.value.name.trim(),
      heartbeat_interval: Number(createForm.value.heartbeat_interval)
    }

    await api.post('/admin/product/', payload)

    // 立即关闭模态框和显示成功消息
    showCreateModal.value = false
    Message.success('产品创建成功')

    // 重置表单
    createForm.value = {
      product_code: '',
      name: '',
      heartbeat_interval: 3600
    }

    // 立即关闭加载状态，用户可以继续操作
    isLoading.value = false

    // 在后台异步刷新列表（不使用await，不阻塞）
    fetchProducts()
  } catch (error: any) {
    Message.error(error.response?.data?.detail || '产品创建失败')
    isLoading.value = false
  }
}

// 显示编辑模态框
const openEditModal = (product: any) => {
  editForm.value = {
    id: product.id,
    name: product.name,
    heartbeat_interval: product.heartbeat_interval,
    status: product.status
  }
  showEditModal.value = true
}

// 更新产品
const updateProduct = async () => {
  isLoading.value = true
  try {
    await api.put(`/admin/product/${editForm.value.id}`, editForm.value)
    showEditModal.value = false
    Message.success('产品更新成功')
    fetchProducts()
  } catch (error) {
    Message.error('产品更新失败')
  } finally {
    isLoading.value = false
  }
}

// 确认删除
const confirmDelete = async (product: any) => {
  const confirmed = await Dialog.confirm({
    title: '确认删除',
    content: `确定要删除产品 "${product.name}" 吗？此操作不可恢复。`
  })

  if (confirmed) {
    await deleteProduct(product.id)
  }
}

// 删除产品
const deleteProduct = async (id: number) => {
  isLoading.value = true
  try {
    await api.delete(`/admin/product/${id}`)
    Message.success('产品删除成功')
    fetchProducts()
  } catch (error) {
    Message.error('产品删除失败')
  } finally {
    isLoading.value = false
  }
}

// 页面挂载时获取产品列表
onMounted(() => {
  fetchProducts()
})
</script>

<style scoped>
.products-page {
  width: 100%;
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.add-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background-color: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s ease;
}

.add-btn:hover {
  background-color: #2563eb;
}

.add-btn :deep(svg) {
  width: 16px;
  height: 16px;
}

/* 工具栏 */
.toolbar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-box {
  position: relative;
  flex: 1;
  max-width: 300px;
}

.search-icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #94a3b8;
}

.search-icon :deep(svg) {
  width: 16px;
  height: 16px;
}

.search-box input {
  width: 100%;
  padding: 10px 12px 10px 36px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s ease;
}

.search-box input:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.filter-select {
  padding: 10px 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 14px;
  background-color: #fff;
  cursor: pointer;
  transition: border-color 0.2s ease;
}

.filter-select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.refresh-btn {
  padding: 10px;
  background-color: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s ease;
}

.refresh-btn:hover:not(:disabled) {
  background-color: #f8fafc;
  border-color: #3b82f6;
}

.refresh-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.refresh-btn :deep(svg) {
  width: 16px;
  height: 16px;
}

/* 表格容器 */
.products-table-wrapper {
  background-color: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 6px 8px;
  box-shadow: 0 1px 2px rgba(16, 24, 40, 0.04);
  overflow: hidden;
}

.products-table {
  width: 100%;
  border-collapse: collapse;
}

.products-table th,
.products-table td {
  padding: 13px 16px;
  text-align: left;
  border-bottom: 1px solid #f0f1f3;
}

.products-table tbody tr {
  transition: background-color 0.1s ease;
}

.products-table tbody tr:hover {
  background-color: #fafafa;
}

.products-table th {
  font-weight: 500;
  font-size: 12.5px;
  color: #9ca3af;
  background-color: transparent;
  white-space: nowrap;
}

.products-table td code {
  background-color: #f1f5f9;
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 13px;
  color: #334155;
}

.status-badge {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge :deep(svg) {
  width: 14px;
  height: 14px;
}

.status-badge.enabled {
  background-color: #ecfdf5;
  color: #047857;
}

.status-badge.disabled {
  background-color: #fef2f2;
  color: #b91c1c;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.key-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  background-color: #fff;
  color: #475569;
  transition: background-color 0.2s ease, color 0.2s ease;
}

.key-btn:hover {
  background-color: #f6f7f9;
  color: #111827;
}

.key-btn :deep(svg) {
  width: 14px;
  height: 14px;
}

.edit-btn,
.delete-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s ease;
}

.edit-btn :deep(svg),
.delete-btn :deep(svg) {
  width: 14px;
  height: 14px;
}

.edit-btn {
  background-color: #3b82f6;
  color: #fff;
}

.edit-btn:hover {
  background-color: #2563eb;
}

.delete-btn {
  background-color: #ef4444;
  color: #fff;
}

.delete-btn:hover:not(:disabled) {
  background-color: #dc2626;
}

.delete-btn:disabled {
  background-color: #fecaca;
  cursor: not-allowed;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: #64748b;
}

.empty-icon {
  font-size: 64px;
  color: #cbd5e1;
  margin-bottom: 16px;
}

.empty-icon :deep(svg) {
  width: 64px;
  height: 64px;
}

.empty-state p {
  font-size: 16px;
  margin-bottom: 20px;
}

.empty-action {
  padding: 10px 20px;
  background-color: #3b82f6;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s ease;
}

.empty-action:hover {
  background-color: #2563eb;
}

/* 分页 */
.pagination {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
  padding-top: 20px;
  border-top: 1px solid #e2e8f0;
}

.pagination-info {
  font-size: 14px;
  color: #64748b;
}

.pagination-controls {
  display: flex;
  align-items: center;
  gap: 8px;
}

.page-btn {
  padding: 6px 12px;
  background-color: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
}

.page-btn:hover:not(:disabled) {
  background-color: #f8fafc;
  border-color: #3b82f6;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-numbers {
  display: flex;
  gap: 4px;
}

.page-number {
  min-width: 32px;
  height: 32px;
  padding: 6px;
  background-color: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: all 0.2s ease;
}

.page-number:hover {
  background-color: #f8fafc;
  border-color: #3b82f6;
}

.page-number.active {
  background-color: #3b82f6;
  border-color: #3b82f6;
  color: #fff;
}

/* 模态框样式 */
.pubkey-body {
  padding: 0 20px 20px;
}

.pubkey-meta {
  font-size: 13px;
  color: #64748b;
  margin: 0 0 12px;
}

.pubkey-pre {
  background-color: #0f172a;
  color: #e2e8f0;
  padding: 16px;
  border-radius: 8px;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 300px;
  overflow-y: auto;
  margin: 0 0 16px;
  font-family: 'Courier New', monospace;
}

.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.modal {
  background-color: #fff;
  border-radius: 8px;
  width: 100%;
  max-width: 500px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2);
  animation: slideUp 0.2s ease;
}

@keyframes slideUp {
  from {
    transform: translateY(20px);
    opacity: 0;
  }
  to {
    transform: translateY(0);
    opacity: 1;
  }
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px;
  border-bottom: 1px solid #e2e8f0;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: #1e293b;
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: #64748b;
  padding: 0;
  width: 30px;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  transition: background-color 0.2s ease;
}

.close-btn:hover {
  background-color: #f1f5f9;
}

.modal-form {
  padding: 20px;
}

.form-group {
  margin-bottom: 20px;
}

.form-group label {
  display: block;
  margin-bottom: 8px;
  font-size: 14px;
  font-weight: 500;
  color: #334155;
}

.form-group input,
.form-group select {
  width: 100%;
  padding: 12px;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  font-size: 14px;
  transition: border-color 0.2s ease;
}

.form-group input:focus,
.form-group select:focus {
  outline: none;
  border-color: #3b82f6;
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}

.form-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 24px;
}

.cancel-btn,
.confirm-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: background-color 0.2s ease;
}

.cancel-btn {
  background-color: #f1f5f9;
  color: #64748b;
}

.cancel-btn:hover {
  background-color: #e2e8f0;
}

.confirm-btn {
  background-color: #3b82f6;
  color: #fff;
}

.confirm-btn:hover:not(:disabled) {
  background-color: #2563eb;
}

.confirm-btn:disabled {
  background-color: #93c5fd;
  cursor: not-allowed;
}
</style>
