<template>
  <section class="page" data-module="array">
    <header class="page-head">
      <div>
        <h2>光伏方阵管理</h2>
        <p class="page-desc">维护方阵，围绕方阵编号、方阵名称、组件型号、组件数量做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记方阵</button>
        <button class="btn" type="button" @click="exportRows">导出光伏方阵清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            暂无光伏方阵数据，可点击右上角「登记方阵」创建第一条记录
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条光伏方阵记录</span>
      <span v-if="noticeMessage" class="ok-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>

    <div v-if="createVisible" class="modal-mask" @click.self="closeCreate">
      <div class="modal">
        <h3>登记方阵</h3>
        <form @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field.name" class="form-item">
            <span>{{ field.name }}<em v-if="field.required">*</em></span>
            <input v-model="createForm[field.name]" :placeholder="`请输入${field.name}`" />
            <small v-if="createErrors[field.name]" class="field-error">{{ createErrors[field.name] }}</small>
          </label>
          <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
          <div class="modal-actions">
            <button class="btn" type="button" @click="closeCreate">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '提交中…' : '确认登记' }}
            </button>
          </div>
        </form>
      </div>
    </div>

    <div v-if="shadingVisible" class="modal-mask" @click.self="closeShading">
      <div class="modal">
        <h3>登记遮挡</h3>
        <p class="modal-desc">
          方阵：{{ shadingRow?.['方阵编号'] ?? '—' }} · {{ shadingRow?.['方阵名称'] ?? '—' }}
        </p>
        <form @submit.prevent="submitShading">
          <label class="form-item">
            <span>遮挡原因<em>*</em></span>
            <textarea
              v-model="shadingForm['遮挡原因']"
              rows="3"
              placeholder="请描述遮挡情况，如树木阴影、积灰、邻近建筑等"
            ></textarea>
            <small v-if="shadingErrors['遮挡原因']" class="field-error">{{ shadingErrors['遮挡原因'] }}</small>
          </label>
          <p v-if="dialogError" class="error-text">{{ dialogError }}</p>
          <div class="modal-actions">
            <button class="btn" type="button" @click="closeShading">取消</button>
            <button class="btn primary" type="submit" :disabled="submitting">
              {{ submitting ? '提交中…' : '确认登记' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/array'
const columns = ["方阵编号", "方阵名称", "组件型号", "组件数量", "安装倾角", "朝向方位", "所属电站", "方阵状态"]
const actions = ["提交验收", "登记遮挡", "拆除方阵"]
const createFields = [
  { name: "方阵编号", required: true },
  { name: "方阵名称", required: true },
  { name: "组件型号", required: true },
  { name: "组件数量", required: false },
  { name: "安装倾角", required: false },
  { name: "朝向方位", required: false },
  { name: "所属电站", required: false },
]
const filterParamMap: Record<string, string> = { "方阵编号": "keyword", "方阵名称": "name", "组件型号": "model" }

const stats = ref([{"label": "在运方阵", "value": 0}, {"label": "遮挡异常方阵", "value": 0}, {"label": "组件总块数", "value": 0}])

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const createVisible = ref(false)
const createForm = ref<Record<string, string>>({})
const createErrors = ref<Record<string, string>>({})
const shadingVisible = ref(false)
const shadingRow = ref<Row | null>(null)
const shadingForm = ref<Record<string, string>>({})
const shadingErrors = ref<Record<string, string>>({})
const dialogError = ref('')
const submitting = ref(false)

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = {}
  createErrors.value = {}
  dialogError.value = ''
  createVisible.value = true
}

function closeCreate() {
  createVisible.value = false
}

function openShading(row: Row) {
  shadingRow.value = row
  shadingForm.value = {}
  shadingErrors.value = {}
  dialogError.value = ''
  shadingVisible.value = true
}

function closeShading() {
  shadingVisible.value = false
}

async function parsePayload(response: Response): Promise<{ ok?: boolean; message?: string } | null> {
  return (await response.json().catch(() => null)) as { ok?: boolean; message?: string } | null
}

async function submitCreate() {
  const errors: Record<string, string> = {}
  for (const field of createFields) {
    if (field.required && !(createForm.value[field.name] ?? '').trim()) {
      errors[field.name] = `请填写${field.name}`
    }
  }
  createErrors.value = errors
  if (Object.keys(errors).length) {
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    const values: Record<string, string> = {}
    for (const field of createFields) {
      const raw = (createForm.value[field.name] ?? '').trim()
      if (raw) {
        values[field.name] = raw
      }
    }
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await parsePayload(response)
    if (!response.ok || !payload?.ok) {
      dialogError.value = payload?.message ?? '方阵登记未生效，请稍后重试'
      return
    }
    createVisible.value = false
    noticeMessage.value = payload.message ?? '方阵已登记'
    await Promise.all([reload(), reloadStats()])
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '方阵登记失败'
  } finally {
    submitting.value = false
  }
}

async function submitShading() {
  const reason = (shadingForm.value['遮挡原因'] ?? '').trim()
  shadingErrors.value = reason ? {} : { "遮挡原因": '请填写遮挡原因' }
  if (!reason) {
    return
  }
  const row = shadingRow.value
  if (!row) {
    return
  }
  submitting.value = true
  dialogError.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action: '登记遮挡', "遮挡原因": reason } }),
    })
    const payload = await parsePayload(response)
    if (!response.ok || !payload?.ok) {
      dialogError.value = payload?.message ?? '遮挡登记未生效，请稍后重试'
      return
    }
    shadingVisible.value = false
    noticeMessage.value = payload.message ?? '方阵已登记遮挡'
    await Promise.all([reload(), reloadStats()])
  } catch (error) {
    dialogError.value = error instanceof Error ? error.message : '遮挡登记失败'
  } finally {
    submitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  if (action === '登记遮挡') {
    openShading(row)
    return
  }
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action } }),
    })
    const payload = await parsePayload(response)
    if (!response.ok || !payload?.ok) {
      throw new Error(payload?.message ?? `方阵${action}未生效，请稍后重试`)
    }
    noticeMessage.value = payload.message ?? `方阵已${action}`
    await Promise.all([reload(), reloadStats()])
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '光伏方阵操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  for (const [field, value] of Object.entries(filters.value)) {
    const key = filterParamMap[field]
    const keyword = value.trim()
    if (key && keyword) {
      query.set(key, keyword)
    }
  }
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('方阵列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '光伏方阵列表读取失败'
  }
}

async function reloadStats() {
  try {
    const response = await request(`${ENDPOINT}/stats`)
    if (!response.ok) {
      return
    }
    const payload = await response.json()
    stats.value = payload.items ?? stats.value
  } catch {
    // 统计卡片读取失败不阻断列表展示
  }
}

onMounted(() => {
  void reload()
  void reloadStats()
})
</script>

<style scoped>
.modal-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.modal {
  width: 420px;
  max-width: calc(100vw - 32px);
  background: #fff;
  border-radius: 10px;
  padding: 18px 20px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
}
.modal h3 {
  margin: 0 0 12px;
  font-size: 16px;
}
.modal-desc {
  margin: 0 0 10px;
  color: var(--muted);
  font-size: 13px;
}
.form-item {
  display: block;
  margin-bottom: 10px;
  font-size: 13px;
}
.form-item span {
  display: block;
  margin-bottom: 4px;
  color: var(--muted);
}
.form-item em {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.form-item input,
.form-item textarea {
  width: 100%;
  border: 1px solid var(--border);
  border-radius: 6px;
  padding: 6px 8px;
  font-size: 13px;
  font-family: inherit;
}
.field-error {
  display: block;
  margin-top: 4px;
  color: #b42318;
  font-size: 12px;
}
.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 14px;
}
.ok-text {
  color: #067647;
}
.empty-state {
  padding: 28px 0;
}
</style>
