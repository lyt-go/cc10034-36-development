/** 纯前端数据层的公共类型：与全栈版后端返回的结构保持一致，换回后端时页面不用改。 */

export type EntryRow = {
  id: number
  status: string
  pending: boolean
  abnormal: boolean
  [field: string]: string | number | boolean
}

export type ModuleMeta = {
  key: string
  name: string
  entity: string
  desc: string
  fields: string[]
  statuses: string[]
  actions: string[]
  actionTargets: Record<string, string>
  metrics: string[]
  optionalFields?: string[]
}

export type PageResult = {
  items: EntryRow[]
  total: number
  page: number
  size: number
}

export type ActionResult = {
  ok: boolean
  message: string
}

export type OverviewResult = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
}

/** 授权结清面板：单条访问的核对结论。 */
export type SettlementLine = {
  记录编号: string
  访问主体: string
  访问时间: string
  回执编号: string
  迟到: boolean
  处理: string
}

/** 授权结清回执。 */
export type SettlementReceipt = {
  回执编号: string
  申请编号: string
  授权版本: string
  结清时间: string
  计入数量: number
  未决数量: number
  重复回执数: number
  明细: SettlementLine[]
}

/** 结清面板：未结清时给出核对预览，已结清时返回回执。 */
export type SettlementPanel = {
  申请编号: string
  授权版本: string
  状态: string
  有效期起: string
  有效期止: string
  可结清: boolean
  已确认: SettlementLine[]
  未决: SettlementLine[]
  重复回执: SettlementLine[]
  结清回执: SettlementReceipt | null
}
