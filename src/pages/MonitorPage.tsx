import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Network,
  MessageSquare,
  Image,
  Server,
  Activity,
  CheckCircle,
  AlertTriangle,
  XCircle,
  RefreshCw,
} from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
// 类型
// ─────────────────────────────────────────────────────────────────────────────

interface ServiceStatus {
  name: string
  status: 'online' | 'degraded' | 'offline'
  latency?: string
  details?: string
}

interface MetricCard {
  label: string
  value: string
  change?: string
  trend?: 'up' | 'down' | 'stable'
}

// ─────────────────────────────────────────────────────────────────────────────
// 模拟数据
// ─────────────────────────────────────────────────────────────────────────────

const ROUTER_SERVICES: ServiceStatus[] = [
  { name: 'SenseNova-U1', status: 'online', latency: '320ms', details: '路由池主模型' },
  { name: 'DeepSeek-V4-Flash', status: 'online', latency: '180ms', details: '快速对话' },
  { name: 'GLM-4', status: 'online', latency: '450ms', details: '备用模型' },
  { name: 'NVIDIA NIM', status: 'online', latency: '280ms', details: 'GPU 推理' },
  { name: 'SiliconFlow', status: 'online', latency: '350ms', details: '文本/图片' },
  { name: 'Qwen2.5-7B', status: 'degraded', latency: '>1s', details: '本地 Ollama' },
]

const AI_METRICS: MetricCard[] = [
  { label: '今日对话', value: '1,247', change: '+12%', trend: 'up' },
  { label: '平均响应', value: '380ms', change: '-20ms', trend: 'down' },
  { label: '成功率', value: '99.2%', change: '+0.3%', trend: 'up' },
]

const IMAGE_METRICS: MetricCard[] = [
  { label: '今日生图', value: '86', change: '+8', trend: 'up' },
  { label: '平均耗时', value: '12.5s', change: '-1.2s', trend: 'down' },
  { label: 'GPU 队列', value: '0', change: '-', trend: 'stable' },
]

const VM_METRICS: MetricCard[] = [
  { label: 'CPU', value: '23%', change: '正常', trend: 'stable' },
  { label: '内存', value: '1.8/4 GB', change: '45%', trend: 'stable' },
  { label: '磁盘', value: '12/40 GB', change: '30%', trend: 'stable' },
  { label: '网络', value: '12 MB/s', change: '入站', trend: 'stable' },
]

// ─────────────────────────────────────────────────────────────────────────────
// 状态指示器
// ─────────────────────────────────────────────────────────────────────────────

function StatusDot({ status }: { status: ServiceStatus['status'] }) {
  const color = status === 'online' ? 'var(--ios-green)' : status === 'degraded' ? 'var(--ios-orange)' : 'var(--ios-red)'
  const Icon = status === 'online' ? CheckCircle : status === 'degraded' ? AlertTriangle : XCircle
  return <Icon size={14} style={{ color }} />
}

// ─────────────────────────────────────────────────────────────────────────────
// Metric Card
// ─────────────────────────────────────────────────────────────────────────────

function MetricRow({ metrics }: { metrics: MetricCard[] }) {
  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
      {metrics.map((m) => (
        <div
          key={m.label}
          className="ios-widget-glass"
          style={{ padding: '10px 8px', textAlign: 'center' }}
        >
          <div style={{ fontSize: 11, color: 'var(--ios-gray)', marginBottom: 4 }}>{m.label}</div>
          <div style={{ fontSize: 18, fontWeight: 700, color: 'var(--realm-text)' }}>{m.value}</div>
          {m.change && (
            <div
              style={{
                fontSize: 10,
                color: m.trend === 'up' ? 'var(--ios-green)' : m.trend === 'down' ? 'var(--ios-red)' : 'var(--ios-gray)',
                marginTop: 2,
              }}
            >
              {m.change}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 监控页
// ─────────────────────────────────────────────────────────────────────────────

export default function MonitorPage() {
  const [activeSection, setActiveSection] = useState<'router' | 'chat' | 'image' | 'vm'>('router')
  const [refreshing, setRefreshing] = useState(false)

  const handleRefresh = () => {
    setRefreshing(true)
    setTimeout(() => setRefreshing(false), 800)
  }

  return (
    <div className="ios-page" style={{ display: 'flex', flexDirection: 'column' }}>
      {/* ── Navigation ──────────────────────────────────────────────── */}
      <div className="ios-safe-top" />
      <div className="ios-navbar" style={{ padding: '8px 16px 4px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Server size={18} style={{ color: 'var(--ios-purple)' }} />
          <span style={{ fontSize: 17, fontWeight: 600, color: 'var(--realm-text)' }}>
            监控面板
          </span>
        </div>
        <motion.button
          onClick={handleRefresh}
          whileTap={{ scale: 0.9 }}
          animate={{ rotate: refreshing ? 360 : 0 }}
          transition={{ duration: 0.5, ease: 'linear' }}
          style={{
            width: 28,
            height: 28,
            borderRadius: 14,
            background: 'var(--ios-gray5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            border: 'none',
            cursor: 'pointer',
          }}
        >
          <RefreshCw size={14} style={{ color: 'var(--ios-blue)' }} />
        </motion.button>
      </div>

      {/* ── 分区切换 ────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 6, padding: '4px 16px 12px', overflow: 'auto', scrollbarWidth: 'none' }}>
        {[
          { id: 'router' as const, label: '路由池', icon: Network },
          { id: 'chat' as const, label: 'AI 聊天', icon: MessageSquare },
          { id: 'image' as const, label: 'AI 生图', icon: Image },
          { id: 'vm' as const, label: 'VM 状况', icon: Activity },
        ].map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            className={`ios-pill ${activeSection === id ? 'active' : ''}`}
            onClick={() => setActiveSection(id)}
            style={{ display: 'flex', alignItems: 'center', gap: 4, flexShrink: 0 }}
          >
            <Icon size={12} />
            {label}
          </button>
        ))}
      </div>

      {/* ── 内容 ────────────────────────────────────────────────────── */}
      <div className="ios-scroll" style={{ flex: 1, padding: '0 16px 16px' }}>
        <AnimatePresence mode="wait">
          <motion.div
            key={activeSection}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -8 }}
            transition={{ duration: 0.2 }}
          >
            {/* 路由池 */}
            {activeSection === 'router' && (
              <div>
                <MetricRow metrics={AI_METRICS} />
                <div style={{ marginTop: 16 }}>
                  <div className="ios-list">
                    {ROUTER_SERVICES.map((svc) => (
                      <div key={svc.name} className="ios-list-item" style={{ cursor: 'default' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                          <StatusDot status={svc.status} />
                          <div>
                            <div style={{ fontSize: 14, fontWeight: 500, color: 'var(--realm-text)' }}>
                              {svc.name}
                            </div>
                            <div style={{ fontSize: 11, color: 'var(--ios-gray)' }}>
                              {svc.details}
                            </div>
                          </div>
                        </div>
                        <span style={{ fontSize: 12, color: 'var(--ios-gray)' }}>
                          {svc.latency}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {/* AI 聊天 */}
            {activeSection === 'chat' && (
              <div>
                <MetricRow metrics={AI_METRICS} />
                <div className="ios-widget-glass" style={{ marginTop: 16, padding: 16 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--realm-text)', marginBottom: 12 }}>
                    模型路由策略
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--ios-gray)', lineHeight: 1.6 }}>
                    L1: DeepSeek-V4-Flash（主）<br />
                    L2: SenseNova-U1（fallback）<br />
                    L3: GLM-4（二级 fallback）<br />
                    L4: Qwen2.5-7B（本地兜底）
                  </div>
                </div>
              </div>
            )}

            {/* AI 生图 */}
            {activeSection === 'image' && (
              <div>
                <MetricRow metrics={IMAGE_METRICS} />
                <div className="ios-widget-glass" style={{ marginTop: 16, padding: 16 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--realm-text)', marginBottom: 12 }}>
                    生图路由链路
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--ios-gray)', lineHeight: 1.6 }}>
                    L1: PAI-EAS SDWebUI（GPU quota=0 ⚠️）<br />
                    L2: SenseNova-U1（图片）<br />
                    L3: SiliconFlow-ZImage（fallback）
                  </div>
                </div>
              </div>
            )}

            {/* VM */}
            {activeSection === 'vm' && (
              <div>
                <MetricRow metrics={VM_METRICS} />
                <div className="ios-widget-glass" style={{ marginTop: 16, padding: 16 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--realm-text)', marginBottom: 12 }}>
                    GCP VM 信息
                  </div>
                  <div style={{ fontSize: 12, color: 'var(--ios-gray)', lineHeight: 1.6 }}>
                    地址: 35.212.211.245<br />
                    系统: Ubuntu<br />
                    运行时长: 持续在线<br />
                    上次更新: 实时
                  </div>
                </div>
              </div>
            )}
          </motion.div>
        </AnimatePresence>
      </div>
    </div>
  )
}