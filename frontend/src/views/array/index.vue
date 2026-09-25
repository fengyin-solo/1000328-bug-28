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
              :disabled="actionPending"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">
            <template v-if="loading">方阵数据加载中…</template>
            <template v-else-if="loadFailed">方阵列表读取失败，表头仍保留；请检查后端服务后刷新重试</template>
            <template v-else-if="hasFilters">当前筛选条件下没有匹配的光伏方阵，可重置条件后重新查询</template>
            <template v-else>暂无光伏方阵数据，可点击右上角「登记方阵」新增第一条记录</template>
          </td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条光伏方阵记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="noticeMessage" class="ok-text">{{ noticeMessage }}</span>
    </footer>

    <!-- 登记方阵弹窗 -->
    <div v-if="createVisible" class="dialog-mask" @click.self="closeCreate">
      <div class="dialog" role="dialog" aria-label="登记方阵">
        <header class="dialog-head">
          <h3>登记方阵</h3>
          <button class="link" type="button" @click="closeCreate">关闭</button>
        </header>
        <form class="dialog-body" @submit.prevent="submitCreate">
          <label v-for="field in createFields" :key="field.name" class="form-item">
            <span>{{ field.label }}<em v-if="field.required" class="required">*</em></span>
            <input v-model="createForm[field.name]" :placeholder="field.placeholder" />
            <small v-if="fieldErrors[field.name]" class="form-error">{{ fieldErrors[field.name] }}</small>
          </label>
          <p v-if="createError" class="error-text dialog-error">{{ createError }}</p>
          <footer class="dialog-foot">
            <button class="btn" type="button" @click="closeCreate">取消</button>
            <button class="btn primary" type="submit" :disabled="createSubmitting">
              {{ createSubmitting ? '提交中…' : '确认登记' }}
            </button>
          </footer>
        </form>
      </div>
    </div>

    <!-- 登记遮挡弹窗 -->
    <div v-if="shadeVisible" class="dialog-mask" @click.self="closeShade">
      <div class="dialog" role="dialog" aria-label="登记遮挡">
        <header class="dialog-head">
          <h3>登记遮挡<span class="dialog-sub">{{ shadeTarget?.['方阵编号'] ?? '' }}</span></h3>
          <button class="link" type="button" @click="closeShade">关闭</button>
        </header>
        <form class="dialog-body" @submit.prevent="submitShade">
          <label class="form-item">
            <span>遮挡原因<em class="required">*</em></span>
            <input v-model="shadeForm.遮挡原因" placeholder="如：树木遮挡、建筑阴影、组件积灰" />
            <small v-if="shadeErrors.遮挡原因" class="form-error">{{ shadeErrors.遮挡原因 }}</small>
          </label>
          <label class="form-item">
            <span>遮挡说明</span>
            <textarea v-model="shadeForm.遮挡说明" rows="3" placeholder="补充遮挡位置、影响范围等（选填）"></textarea>
          </label>
          <p v-if="shadeError" class="error-text dialog-error">{{ shadeError }}</p>
          <footer class="dialog-foot">
            <button class="btn" type="button" @click="closeShade">取消</button>
            <button class="btn primary" type="submit" :disabled="shadeSubmitting">
              {{ shadeSubmitting ? '提交中…' : '确认登记遮挡' }}
            </button>
          </footer>
        </form>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | boolean | null>

interface ActionResult {
  ok: boolean
  message: string
  entry?: Row | null
}

interface CreateField {
  name: string
  label: string
  placeholder: string
  required: boolean
}

const ENDPOINT = '/api/array'
const columns = ["方阵编号", "方阵名称", "组件型号", "组件数量", "安装倾角", "朝向方位", "所属电站", "方阵状态"]
const actions = ["提交验收", "登记遮挡", "拆除方阵"]
const requiredFields = ["方阵编号", "方阵名称", "组件型号"]
const createFields: CreateField[] = [
  { name: "方阵编号", label: "方阵编号", placeholder: "如 ARRA-0004", required: true },
  { name: "方阵名称", label: "方阵名称", placeholder: "如 1号光伏方阵", required: true },
  { name: "组件型号", label: "组件型号", placeholder: "如 JKM550M-72HL4", required: true },
  { name: "组件数量", label: "组件数量", placeholder: "正整数，选填", required: false },
  { name: "安装倾角", label: "安装倾角", placeholder: "如 30°", required: false },
  { name: "朝向方位", label: "朝向方位", placeholder: "如 正南", required: false },
  { name: "所属电站", label: "所属电站", placeholder: "如 1号光伏电站", required: false },
]

const rows = ref<Row[]>([])
const total = ref(0)
const loading = ref(false)
const loadFailed = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const createVisible = ref(false)
const createSubmitting = ref(false)
const createForm = ref<Record<string, string>>({})
const fieldErrors = ref<Record<string, string>>({})
const createError = ref('')

const shadeVisible = ref(false)
const shadeSubmitting = ref(false)
const shadeTarget = ref<Row | null>(null)
const shadeForm = ref({ 遮挡原因: '', 遮挡说明: '' })
const shadeErrors = ref<Record<string, string>>({})
const shadeError = ref('')

const actionPending = ref(false)

const hasFilters = computed(() =>
  Object.values(filters.value).some((value) => String(value ?? '').trim() !== ''),
)

function statusOf(row: Row): string {
  return String(row['方阵状态'] ?? row['status'] ?? '')
}

// 统计卡片直接由列表数据计算，遮挡异常数量始终与列表保持一致
const stats = computed(() => [
  { label: "在运方阵", value: rows.value.filter((row) => statusOf(row) === '已投运').length },
  { label: "遮挡异常方阵", value: rows.value.filter((row) => statusOf(row) === '遮挡异常').length },
  { label: "组件总块数", value: rows.value.reduce((sum, row) => sum + (Number(row['组件数量']) || 0), 0) },
])

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = Object.fromEntries(createFields.map((field) => [field.name, '']))
  fieldErrors.value = {}
  createError.value = ''
  createVisible.value = true
}

function closeCreate() {
  if (createSubmitting.value) return
  createVisible.value = false
}

function validateCreate(): boolean {
  const errors: Record<string, string> = {}
  for (const field of requiredFields) {
    if (!String(createForm.value[field] ?? '').trim()) {
      errors[field] = `${field}为必填项，请填写后再提交`
    }
  }
  const count = String(createForm.value['组件数量'] ?? '').trim()
  if (count && (!/^\d+$/.test(count) || Number(count) <= 0)) {
    errors['组件数量'] = '组件数量需为大于 0 的正整数'
  }
  fieldErrors.value = errors
  return Object.keys(errors).length === 0
}

async function submitCreate() {
  // 连点确认时只提交一次，重复登记由后端按方阵编号再兜底合并
  if (createSubmitting.value) return
  createError.value = ''
  if (!validateCreate()) return
  createSubmitting.value = true
  try {
    const values: Record<string, string | number> = {}
    for (const field of createFields) {
      const raw = String(createForm.value[field.name] ?? '').trim()
      if (!raw) continue
      values[field.name] = field.name === '组件数量' ? Number(raw) : raw
    }
    const result = await postJson(ENDPOINT, { values })
    if (!result.ok) {
      mapMissingFields(result.message)
      createError.value = result.message || '方阵登记失败，请稍后重试'
      return
    }
    createVisible.value = false
    noticeMessage.value = result.message || '方阵已登记'
    await reload()
  } catch (error) {
    createError.value = error instanceof Error ? error.message : '方阵登记失败'
  } finally {
    createSubmitting.value = false
  }
}

function mapMissingFields(message: string) {
  for (const field of requiredFields) {
    if (message.includes(field)) {
      fieldErrors.value[field] = `${field}为必填项，请填写后再提交`
    }
  }
}

function openShade(row: Row) {
  shadeTarget.value = row
  shadeForm.value = { 遮挡原因: '', 遮挡说明: '' }
  shadeErrors.value = {}
  shadeError.value = ''
  shadeVisible.value = true
}

function closeShade() {
  if (shadeSubmitting.value) return
  shadeVisible.value = false
}

async function submitShade() {
  if (shadeSubmitting.value || !shadeTarget.value) return
  shadeError.value = ''
  const reason = shadeForm.value.遮挡原因.trim()
  if (!reason) {
    shadeErrors.value = { 遮挡原因: '遮挡原因为必填项，请填写后再提交' }
    return
  }
  shadeErrors.value = {}
  shadeSubmitting.value = true
  try {
    const note = shadeForm.value.遮挡说明.trim()
    const result = await postJson(`${ENDPOINT}/${shadeTarget.value.id}/actions`, {
      values: { action: '登记遮挡', 遮挡原因: reason },
      remark: note || undefined,
    })
    if (!result.ok) {
      shadeError.value = result.message || '遮挡登记未生效，请稍后重试'
      return
    }
    shadeVisible.value = false
    noticeMessage.value = result.message || '方阵已登记遮挡'
    await reload()
  } catch (error) {
    shadeError.value = error instanceof Error ? error.message : '遮挡登记失败'
  } finally {
    shadeSubmitting.value = false
  }
}

async function runAction(action: string, row: Row) {
  if (action === '登记遮挡') {
    openShade(row)
    return
  }
  if (actionPending.value) return
  errorMessage.value = ''
  noticeMessage.value = ''
  actionPending.value = true
  try {
    const result = await postJson(`${ENDPOINT}/${row.id}/actions`, { values: { action } })
    if (!result.ok) {
      errorMessage.value = result.message || '光伏方阵动作未生效，请稍后重试'
      return
    }
    noticeMessage.value = result.message
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '光伏方阵操作失败'
  } finally {
    actionPending.value = false
  }
}

async function postJson(path: string, payload: Record<string, unknown>): Promise<ActionResult> {
  const response = await request(path, {
    method: 'POST',
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    throw new Error(`接口返回 ${response.status}，数据未更新`)
  }
  return (await response.json()) as ActionResult
}

async function reload() {
  errorMessage.value = ''
  loading.value = true
  loadFailed.value = false
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('方阵列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    loadFailed.value = true
    errorMessage.value = error instanceof Error ? error.message : '光伏方阵列表读取失败'
  } finally {
    loading.value = false
  }
}

onMounted(reload)
</script>

<style scoped>
.dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 20;
}
.dialog {
  width: 440px;
  max-width: calc(100vw - 32px);
  background: #fff;
  border-radius: 10px;
  padding: 16px 18px;
  box-shadow: 0 12px 32px rgba(15, 23, 42, 0.18);
}
.dialog-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}
.dialog-head h3 {
  margin: 0;
  font-size: 15px;
}
.dialog-sub {
  margin-left: 8px;
  color: var(--muted);
  font-size: 12px;
  font-weight: normal;
}
.dialog-body {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.form-item span {
  display: block;
  font-size: 12px;
  color: var(--muted);
  margin-bottom: 4px;
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
.required {
  color: #b42318;
  font-style: normal;
  margin-left: 2px;
}
.form-error {
  display: block;
  color: #b42318;
  font-size: 12px;
  margin-top: 2px;
}
.dialog-error {
  margin: 0;
  font-size: 12px;
}
.dialog-foot {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 2px;
}
.ok-text {
  color: #027a48;
}
.btn:disabled,
.link:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
