<template>
  <section class="page" :data-module="meta.key">
    <header class="page-head">
      <div>
        <h2>{{ meta.name }}</h2>
        <p class="page-desc">{{ meta.desc }}</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" data-testid="open-create" type="button" @click="openCreate">
          登记{{ meta.entity }}
        </button>
        <button class="btn" data-testid="export" type="button" @click="exportRows">
          导出{{ meta.name }}清单
        </button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <p class="status-legend">
      <span v-for="item in statusSummary" :key="item.status" class="legend-item">
        {{ item.status }}：{{ item.count }}
      </span>
    </p>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :data-testid="`filter-${field}`" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" data-testid="query" type="submit">查询</button>
      <button class="btn ghost" data-testid="reset" type="button" @click="resetFilters">重置条件</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in meta.fields" :key="column">{{ column }}</th>
          <th>当前状态</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)" :data-testid="`row-${row.id}`" :data-status="String(row.status)">
          <td v-for="column in meta.fields" :key="column">{{ row[column] ?? '—' }}</td>
          <td>{{ row.status }}</td>
          <td class="row-actions">
            <button
              v-for="action in meta.actions"
              :key="action"
              class="link"
              type="button"
              :data-testid="`action-${row.id}-${action}`"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
            <button
              v-if="meta.key === 'grant_approval'"
              class="link"
              type="button"
              :data-testid="`settlement-${row.id}`"
              @click="openSettlement(row)"
            >
              结清面板
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="meta.fields.length + 2" class="empty-state">
            暂无{{ meta.name }}数据，可先登记{{ meta.entity }}
          </td>
        </tr>
      </tbody>
    </table>

    <div v-if="showCreate" class="modal-backdrop" data-testid="create-modal">
      <form class="modal" @submit.prevent="submitCreate">
        <h3>登记{{ meta.entity }}</h3>
        <label v-for="field in meta.fields" :key="field" class="create-field">
          <span>{{ field }}</span>
          <input
            v-model="createValues[field]"
            :data-testid="`create-${field}`"
            :required="!meta.optionalFields?.includes(field)"
          />
        </label>
        <div class="page-actions">
          <button class="btn" type="button" @click="showCreate = false">取消</button>
          <button class="btn primary" data-testid="submit-create" type="submit" :disabled="creating">
            {{ creating ? '提交中…' : '确认登记' }}
          </button>
        </div>
      </form>
    </div>

    <div v-if="settlement" class="modal-backdrop" data-testid="settlement-panel">
      <div class="modal settlement-modal">
        <h3>授权结清面板</h3>
        <p class="settlement-meta">
          申请编号 {{ settlement.申请编号 }} · 授权版本 {{ settlement.授权版本 }} ·
          状态 {{ settlement.状态 }} · 有效期 {{ settlement.有效期起 }} ~ {{ settlement.有效期止 }}
        </p>

        <template v-if="settlement.结清回执">
          <div class="stat-row">
            <article class="stat-card">
              <span class="stat-label">结清数量（计入本次结清）</span>
              <strong class="stat-value" data-testid="settled-count">{{ settlement.结清回执.计入数量 }}</strong>
            </article>
            <article class="stat-card">
              <span class="stat-label">未决项（仍需复核）</span>
              <strong class="stat-value" data-testid="pending-count">{{ settlement.结清回执.未决数量 }}</strong>
            </article>
            <article class="stat-card">
              <span class="stat-label">重复回执（未多计）</span>
              <strong class="stat-value" data-testid="duplicate-count">{{ settlement.结清回执.重复回执数 }}</strong>
            </article>
          </div>
          <p class="settlement-receipt">
            结清回执 {{ settlement.结清回执.回执编号 }} · 结清时间 {{ settlement.结清回执.结清时间 }}
          </p>
          <table class="data-table">
            <thead>
              <tr><th>记录编号</th><th>访问主体</th><th>访问时间</th><th>回执编号</th><th>回执迟到</th><th>结清处理</th></tr>
            </thead>
            <tbody>
              <tr v-for="line in settlement.结清回执.明细" :key="line.记录编号">
                <td>{{ line.记录编号 }}</td>
                <td>{{ line.访问主体 }}</td>
                <td>{{ line.访问时间 }}</td>
                <td>{{ line.回执编号 }}</td>
                <td>{{ line.迟到 ? '迟到' : '准时' }}</td>
                <td>{{ line.处理 }}</td>
              </tr>
            </tbody>
          </table>
        </template>

        <template v-else>
          <h4>已确认访问（计入本次结清）</h4>
          <table class="data-table" data-testid="settlement-confirmed">
            <thead>
              <tr><th>记录编号</th><th>访问主体</th><th>访问时间</th><th>回执编号</th><th>回执迟到</th><th>结清处理</th></tr>
            </thead>
            <tbody>
              <tr v-for="line in settlement.已确认" :key="line.记录编号">
                <td>{{ line.记录编号 }}</td>
                <td>{{ line.访问主体 }}</td>
                <td>{{ line.访问时间 }}</td>
                <td>{{ line.回执编号 }}</td>
                <td>{{ line.迟到 ? '迟到' : '准时' }}</td>
                <td>{{ line.处理 }}</td>
              </tr>
              <tr v-if="!settlement.已确认.length"><td colspan="6" class="empty-state">暂无已确认访问</td></tr>
            </tbody>
          </table>

          <h4>未决访问（仍需复核）</h4>
          <table class="data-table" data-testid="settlement-pending">
            <thead>
              <tr><th>记录编号</th><th>访问主体</th><th>访问时间</th><th>回执编号</th><th>回执迟到</th><th>结清处理</th></tr>
            </thead>
            <tbody>
              <tr v-for="line in settlement.未决" :key="line.记录编号">
                <td>{{ line.记录编号 }}</td>
                <td>{{ line.访问主体 }}</td>
                <td>{{ line.访问时间 }}</td>
                <td>{{ line.回执编号 }}</td>
                <td>{{ line.迟到 ? '迟到' : '准时' }}</td>
                <td>{{ line.处理 }}</td>
              </tr>
              <tr v-if="!settlement.未决.length"><td colspan="6" class="empty-state">暂无未决访问</td></tr>
            </tbody>
          </table>

          <h4>重复回执（不多计一次）</h4>
          <table class="data-table" data-testid="settlement-duplicates">
            <thead>
              <tr><th>记录编号</th><th>访问主体</th><th>访问时间</th><th>回执编号</th><th>结清处理</th></tr>
            </thead>
            <tbody>
              <tr v-for="line in settlement.重复回执" :key="line.记录编号">
                <td>{{ line.记录编号 }}</td>
                <td>{{ line.访问主体 }}</td>
                <td>{{ line.访问时间 }}</td>
                <td>{{ line.回执编号 }}</td>
                <td>{{ line.处理 }}</td>
              </tr>
              <tr v-if="!settlement.重复回执.length"><td colspan="5" class="empty-state">暂无重复回执</td></tr>
            </tbody>
          </table>
        </template>

        <p v-if="settlementError" class="error-text">{{ settlementError }}</p>
        <div class="page-actions">
          <button class="btn" type="button" data-testid="settlement-close" @click="closeSettlement">关闭</button>
          <button
            v-if="settlement.可结清"
            class="btn primary"
            type="button"
            data-testid="settle-confirm"
            :disabled="settling"
            @click="confirmSettle"
          >
            {{ settling ? '结清中…' : '确认结清' }}
          </button>
        </div>
      </div>
    </div>

    <footer class="page-foot">
      <span>共 {{ total }} 条{{ meta.name }}记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import {
  createEntry,
  downloadEntries,
  listEntries,
  loadSettlement,
  moduleMeta,
  runAction as applyAction,
} from '@/api/backend-service'
import type { EntryRow, SettlementPanel } from '@/data/types'

const props = defineProps<{ moduleKey: string }>()
const meta = moduleMeta(props.moduleKey)
const rows = ref<EntryRow[]>([])
const total = ref(0)
const errorMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = meta.fields.slice(0, 3)
const showCreate = ref(false)
const creating = ref(false)
const createValues = ref<Record<string, string>>({})
const settlement = ref<SettlementPanel | null>(null)
const settlementRowId = ref<number | null>(null)
const settlementError = ref('')
const settling = ref(false)
const stats = computed(() => [
  { label: meta.metrics[0], value: total.value },
  { label: meta.metrics[1], value: rows.value.filter((row) => row.status === meta.statuses[1]).length },
  {
    label: meta.metrics[2],
    value: rows.value.filter((row) => row.status === meta.statuses[meta.statuses.length - 1]).length,
  },
])
const statusSummary = computed(() =>
  meta.statuses.map((status) => ({
    status,
    count: rows.value.filter((row) => String(row.status) === status).length,
  })),
)

function resetFilters() {
  filters.value = {}
  void reload()
}

async function exportRows() {
  errorMessage.value = ''
  try {
    await downloadEntries(meta.key, filters.value)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '导出失败'
  }
}

function openCreate() {
  createValues.value = Object.fromEntries(meta.fields.map((field) => [field, '']))
  errorMessage.value = ''
  showCreate.value = true
}

async function submitCreate() {
  creating.value = true
  errorMessage.value = ''
  try {
    const result = await createEntry(meta.key, createValues.value)
    if (!result.ok) throw new Error(result.message)
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '登记失败'
  } finally {
    creating.value = false
  }
}

async function runAction(action: string, row: EntryRow) {
  errorMessage.value = ''
  try {
    const result = await applyAction(meta.key, Number(row.id), action)
    if (!result.ok) throw new Error(result.message)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '操作失败'
  }
}

async function openSettlement(row: EntryRow) {
  settlementRowId.value = Number(row.id)
  settlementError.value = ''
  try {
    settlement.value = await loadSettlement(meta.key, settlementRowId.value)
  } catch (error) {
    settlementRowId.value = null
    errorMessage.value = error instanceof Error ? error.message : '结清面板读取失败'
  }
}

function closeSettlement() {
  settlement.value = null
  settlementRowId.value = null
  settlementError.value = ''
}

async function confirmSettle() {
  if (settlementRowId.value === null) return
  settling.value = true
  settlementError.value = ''
  try {
    const result = await applyAction(meta.key, settlementRowId.value, '结清授权')
    if (!result.ok) throw new Error(result.message)
    settlement.value = await loadSettlement(meta.key, settlementRowId.value)
    await reload()
  } catch (error) {
    settlementError.value = error instanceof Error ? error.message : '结清失败'
  } finally {
    settling.value = false
  }
}

async function reload() {
  errorMessage.value = ''
  try {
    const payload = await listEntries(meta.key, filters.value)
    rows.value = payload.items
    total.value = payload.total
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '业务列表读取失败'
  }
}

onMounted(reload)
</script>
