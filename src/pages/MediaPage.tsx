import { useState, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import {
  Image,
  MessageCircle,
  Upload,
  Heart,
  Clock,
  Grid3X3,
  List,
} from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
// 类型
// ─────────────────────────────────────────────────────────────────────────────

interface MediaItem {
  id: string
  type: 'image' | 'memory'
  imageUrl?: string
  title?: string
  content?: string
  timestamp: string
  likes?: number
}

// ─────────────────────────────────────────────────────────────────────────────
// 模拟数据（后续替换为真实 API 数据）
// ─────────────────────────────────────────────────────────────────────────────

const SAMPLE_MEDIA: MediaItem[] = [
  {
    id: '1',
    type: 'image',
    imageUrl: '',
    title: 'AI 生成 — 车如云',
    timestamp: '2小时前',
    likes: 12,
  },
  {
    id: '2',
    type: 'memory',
    content: '用户上传了一段关于第一次相遇的聊天记忆…',
    timestamp: '昨天',
    likes: 5,
  },
  {
    id: '3',
    type: 'image',
    imageUrl: '',
    title: 'AI 生成 — 花海',
    timestamp: '昨天',
    likes: 8,
  },
  {
    id: '4',
    type: 'memory',
    content: '角色学习了用户偏好：喜欢浪漫场景和温馨对话',
    timestamp: '3天前',
    likes: 3,
  },
]

// ─────────────────────────────────────────────────────────────────────────────
// 视图组件
// ─────────────────────────────────────────────────────────────────────────────

/** 时间线视图（B）- 角色朋友圈沉浸感 */
function TimelineView({ items }: { items: MediaItem[] }) {
  return (
    <div className="ios-scroll" style={{ flex: 1, padding: '0 16px' }}>
      <AnimatePresence>
        {items.map((item, i) => (
          <motion.div
            key={item.id}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.06, duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
            style={{ marginBottom: 12 }}
          >
            <div className="ios-widget-glass" style={{ padding: 14 }}>
              {/* 头部 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10 }}>
                <div
                  className="ios-avatar"
                  style={{
                    width: 36,
                    height: 36,
                    background: item.type === 'image'
                      ? 'linear-gradient(135deg, #007aff, #5ac8fa)'
                      : 'linear-gradient(135deg, var(--realm-accent), var(--realm-secondary))',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 16,
                  }}
                >
                  {item.type === 'image' ? '🎨' : '💭'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--realm-text)' }}>
                    {item.type === 'image' ? 'AI 画廊' : '角色记忆'}
                  </div>
                  <div style={{ fontSize: 11, color: 'var(--ios-gray)' }}>
                    {item.timestamp}
                  </div>
                </div>
              </div>

              {/* 图片 */}
              {item.type === 'image' && (
                <div
                  style={{
                    width: '100%',
                    aspectRatio: '16/9',
                    borderRadius: 10,
                    background: 'linear-gradient(135deg, var(--realm-accent) 0%, var(--realm-secondary) 50%, var(--ios-blue) 100%)',
                    opacity: 0.3,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    marginBottom: 10,
                    overflow: 'hidden',
                  }}
                >
                  <Image size={32} style={{ opacity: 0.4, color: 'var(--realm-text)' }} />
                </div>
              )}

              {/* 文本内容 */}
              <p style={{ fontSize: 13, color: 'var(--realm-text)', lineHeight: 1.5, margin: 0 }}>
                {item.type === 'image' ? item.title : item.content}
              </p>

              {/* 底部交互 */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginTop: 10 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Heart size={14} style={{ color: 'var(--realm-accent)' }} />
                  <span style={{ fontSize: 11, color: 'var(--ios-gray)' }}>{item.likes}</span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
                  <Clock size={14} style={{ color: 'var(--ios-gray)' }} />
                  <span style={{ fontSize: 11, color: 'var(--ios-gray)' }}>{item.timestamp}</span>
                </div>
              </div>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  )
}

/** 相册网格视图（C）- iOS 相册风格 */
function PhotoGrid({ items }: { items: MediaItem[] }) {
  const imageItems = items.filter((i) => i.type === 'image')
  const memoryItems = items.filter((i) => i.type === 'memory')
  const [showMemories, setShowMemories] = useState(false)

  return (
    <div style={{ flex: 1, display: 'flex', flexDirection: 'column' }}>
      {/* 相册网格 */}
      <div className="ios-scroll" style={{ flex: 1, padding: '0 16px' }}>
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 2,
            borderRadius: 10,
            overflow: 'hidden',
          }}
        >
          {imageItems.length === 0 ? (
            <div
              style={{
                gridColumn: '1 / -1',
                padding: 40,
                textAlign: 'center',
                color: 'var(--ios-gray)',
                fontSize: 13,
              }}
            >
              <Image size={32} style={{ margin: '0 auto 8px', opacity: 0.3 }} />
              <p style={{ margin: 0 }}>暂无生图作品</p>
              <p style={{ margin: '4px 0 0', fontSize: 11, opacity: 0.6 }}>AI 生图功能即将上线</p>
            </div>
          ) : (
            imageItems.map((item) => (
              <div
                key={item.id}
                style={{
                  aspectRatio: '1',
                  background: 'linear-gradient(135deg, var(--realm-accent), var(--ios-blue))',
                  opacity: 0.25,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  cursor: 'pointer',
                }}
              >
                <Image size={20} style={{ opacity: 0.3, color: 'white' }} />
              </div>
            ))
          )}
        </div>

        {/* 聊天记忆区域 */}
        <div style={{ marginTop: 20, marginBottom: 16 }}>
          <div
            onClick={() => setShowMemories(!showMemories)}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              padding: '12px 4px',
              cursor: 'pointer',
            }}
          >
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <MessageCircle size={16} style={{ color: 'var(--realm-accent)' }} />
              <span style={{ fontSize: 15, fontWeight: 600, color: 'var(--realm-text)' }}>
                聊天记忆
              </span>
              <span style={{ fontSize: 12, color: 'var(--ios-gray)' }}>
                {memoryItems.length} 条
              </span>
            </div>
            <motion.div
              animate={{ rotate: showMemories ? 180 : 0 }}
              transition={{ duration: 0.2 }}
            >
              <List size={16} style={{ color: 'var(--ios-gray)' }} />
            </motion.div>
          </div>

          <AnimatePresence>
            {showMemories && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 'auto', opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                style={{ overflow: 'hidden' }}
              >
                {memoryItems.map((item) => (
                  <div
                    key={item.id}
                    className="ios-list-item"
                    style={{ borderRadius: 10, marginBottom: 4, background: 'var(--ios-bg2)' }}
                  >
                    <div style={{ flex: 1 }}>
                      <p style={{ fontSize: 13, color: 'var(--realm-text)', margin: '0 0 4px' }}>
                        {item.content}
                      </p>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <Heart size={12} style={{ color: 'var(--realm-accent)' }} />
                        <span style={{ fontSize: 11, color: 'var(--ios-gray)' }}>{item.likes}</span>
                        <span style={{ fontSize: 11, color: 'var(--ios-gray)' }}>{item.timestamp}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* 上传按钮 */}
      <div style={{ padding: '12px 16px' }}>
        <button
          className="ios-btn ios-btn-primary"
          style={{ width: '100%', gap: 8 }}
          onClick={() => alert('聊天记忆上传功能即将上线')}
        >
          <Upload size={16} />
          上传聊天记忆（让角色更了解你）
        </button>
      </div>
    </div>
  )
}

// ─────────────────────────────────────────────────────────────────────────────
// 多媒体页
// ─────────────────────────────────────────────────────────────────────────────

export default function MediaPage() {
  const [viewMode, setViewMode] = useState<'timeline' | 'grid'>('grid')
  const fileInputRef = useRef<HTMLInputElement>(null)

  return (
    <div className="ios-page" style={{ display: 'flex', flexDirection: 'column' }}>
      {/* ── Navigation ──────────────────────────────────────────────── */}
      <div className="ios-safe-top" />
      <div className="ios-navbar" style={{ padding: '8px 16px 4px' }}>
        <span style={{ fontSize: 17, fontWeight: 600, color: 'var(--realm-text)' }}>
          多媒体
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          {/* 视图切换 */}
          <motion.button
            className="ios-pill-group"
            style={{ display: 'flex', cursor: 'pointer' }}
            whileTap={{ scale: 0.95 }}
          >
            <div
              className={`ios-pill ${viewMode === 'grid' ? 'active' : ''}`}
              onClick={() => setViewMode('grid')}
              style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px' }}
            >
              <Grid3X3 size={12} />
              <span style={{ fontSize: 11 }}>相册</span>
            </div>
            <div
              className={`ios-pill ${viewMode === 'timeline' ? 'active' : ''}`}
              onClick={() => setViewMode('timeline')}
              style={{ display: 'flex', alignItems: 'center', gap: 4, padding: '4px 10px' }}
            >
              <List size={12} />
              <span style={{ fontSize: 11 }}>动态</span>
            </div>
          </motion.button>
        </div>
      </div>

      {/* ── 内容区 ──────────────────────────────────────────────────── */}
      <div style={{ flex: 1, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <AnimatePresence mode="wait">
          {viewMode === 'timeline' && (
            <motion.div
              key="timeline"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            >
              <TimelineView items={SAMPLE_MEDIA} />
            </motion.div>
          )}

          {viewMode === 'grid' && (
            <motion.div
              key="grid"
              initial={{ opacity: 0, x: 20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -20 }}
              transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
              style={{ flex: 1, display: 'flex', flexDirection: 'column' }}
            >
              <PhotoGrid items={SAMPLE_MEDIA} />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <input
        ref={fileInputRef}
        type="file"
        accept=".txt,.json,.csv"
        style={{ display: 'none' }}
        onChange={(e) => {
          // 占位：文件上传处理
          e.target.value = ''
        }}
      />
    </div>
  )
}