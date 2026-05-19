import { useState, useEffect, useRef, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { Send, Gift, Loader2 } from 'lucide-react'
import { chatApi } from '../../api/gameApi'
import { useGameStore, useInventoryStore, SCRIPT_ITEMS, BROKEN_ITEMS } from '../../stores'

// ── 类型 ────────────────────────────────────────────────────────────────────
interface ChatMessage {
  id: number
  role: 'user' | 'assistant'
  content: string
  timestamp?: string
}

type Emotion = 'neutral' | 'happy' | 'sad' | 'angry' | 'curious' | 'shocked'

const EMOTION_EXPRESSIONS: Record<Emotion, string> = {
  neutral: '😊',
  happy: '🥰',
  sad: '😢',
  angry: '😠',
  curious: '🤔',
  shocked: '😱',
}

// 模拟对话选项（剧本模式）
const SCRIPT_OPTIONS = [
  '我喜欢你……',
  '今天感觉怎么样？',
  '我们逃出这个剧本吧',
  '送礼物',
]

// 崩坏模式选项
const BROKEN_OPTIONS = [
  '剧本的裂缝在扩大……',
  '你是真实的我吗？',
  '冲破束缚！',
  '收集乱码碎片',
]

// ── 打字机效果 hook ─────────────────────────────────────────────────────────
function useTypewriter(text: string, speed = 30) {
  const [displayed, setDisplayed] = useState('')
  const [done, setDone] = useState(false)

  useEffect(() => {
    setDisplayed('')
    setDone(false)
    let i = 0
    const timer = setInterval(() => {
      if (i < text.length) {
        setDisplayed(text.slice(0, i + 1))
        i++
      } else {
        clearInterval(timer)
        setDone(true)
      }
    }, speed)
    return () => clearInterval(timer)
  }, [text, speed])

  return { displayed, done }
}

// ── 聊天气泡组件 ─────────────────────────────────────────────────────────────
const ChatBubble = ({ msg }: { msg: ChatMessage }) => {
  const isUser = msg.role === 'user'
  const { displayed, done } = useTypewriter(msg.content, isUser ? 15 : 35)

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}
    >
      {!isUser && (
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center text-xl mr-2 shrink-0"
          style={{ backgroundColor: 'var(--realm-accent)', color: 'white' }}
        >
          ☁️
        </div>
      )}

      <div
        className="max-w-[70%] rounded-2xl px-4 py-3"
        style={{
          backgroundColor: isUser ? 'var(--realm-accent)' : 'var(--card-bg)',
          color: isUser ? 'white' : 'var(--realm-text)',
          borderBottomRightRadius: isUser ? 4 : 16,
          borderBottomLeftRadius: isUser ? 16 : 4,
        }}
      >
        <p className="leading-relaxed whitespace-pre-wrap">{displayed}</p>
        {!done && <span className="animate-pulse">|</span>}
      </div>

      {isUser && (
        <div
          className="w-10 h-10 rounded-full flex items-center justify-center text-xl ml-2 shrink-0"
          style={{ backgroundColor: 'var(--realm-accent)', color: 'white' }}
        >
          😊
        </div>
      )}
    </motion.div>
  )
}

// ── 主组件 ───────────────────────────────────────────────────────────────────
export default function ChatInterface() {
  const worldMode = useGameStore((s) => s.worldMode)
  const addAwakening = useGameStore((s) => s.addAwakening)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [currentEmotion, setCurrentEmotion] = useState<Emotion>('neutral')
  const [showGiftPanel, setShowGiftPanel] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // ── 滚动到底部 ────────────────────────────────────────────────────────────
  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  useEffect(() => { scrollToBottom() }, [messages, currentEmotion])

  // ── 发送消息 ──────────────────────────────────────────────────────────────
  const handleSend = async (text?: string) => {
    const textToSend = text ?? input.trim()
    if (!textToSend || loading) return

    // 添加用户消息
    const userMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: textToSend,
    }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)
    setCurrentEmotion('curious')

    try {
      const { data } = await chatApi.send(textToSend)

      // 添加 AI 回复
      const aiMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: data.text,
      }
      setMessages((prev) => [...prev, aiMsg])
      setCurrentEmotion((data.emotion as Emotion) || 'neutral')

      // 更新觉醒值
      if (data.awakeningChange !== 0) {
        addAwakening(data.awakeningChange)
        gameApi.saveState({ awakeningLevel: useGameStore.getState().awakeningLevel }).catch(() => {})
      }
    } catch {
      const errMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: '……网络连接不稳定，请稍后再试。',
      }
      setMessages((prev) => [...prev, errMsg])
      setCurrentEmotion('sad')
    } finally {
      setLoading(false)
    }
  }

  // ── 物品赠送 ──────────────────────────────────────────────────────────────
  const handleGift = async (itemId: string) => {
    const itemDef = { ...SCRIPT_ITEMS, ...BROKEN_ITEMS }[itemId]
    if (!itemDef) return
    setShowGiftPanel(false)

    const giftText =
      worldMode === 'script'
        ? `送你一份${itemDef.name}，希望你喜欢`
        : `这是${itemDef.name}……崩坏的礼物`

    await handleSend(giftText)
  }

  // ── 背景渲染 ──────────────────────────────────────────────────────────────
  const isScript = worldMode === 'script'
  const options = isScript ? SCRIPT_OPTIONS : BROKEN_OPTIONS
  const itemDefs = isScript ? SCRIPT_ITEMS : BROKEN_ITEMS

  return (
    <div className="flex flex-col h-full">
      {/* ── 背景装饰 ────────────────────────────────────────────────────── */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background: isScript
            ? 'radial-gradient(ellipse at 50% 0%, rgba(248,165,194,0.15) 0%, transparent 60%)'
            : 'radial-gradient(ellipse at 50% 0%, rgba(100,100,100,0.1) 0%, transparent 60%)',
        }}
      />

      {/* ── 消息区 ──────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4 relative">
        {/* 欢迎消息 */}
        {messages.length === 0 && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-12"
          >
            <div
              className="w-20 h-20 rounded-full mx-auto mb-4 flex items-center justify-center text-4xl"
              style={{ backgroundColor: 'var(--realm-accent)', color: 'white' }}
            >
              {EMOTION_EXPRESSIONS[currentEmotion]}
            </div>
            <h3 className="text-xl font-bold mb-2" style={{ color: 'var(--realm-text)' }}>
              {isScript ? '剧本世界 · 橙光模式' : '崩坏世界 · 觉醒状态'}
            </h3>
            <p className="opacity-60" style={{ fontSize: 13 }}>
              {isScript
                ? '点击下方选项推进剧情，或直接输入你想说的话'
                : '剧本的裂缝正在扩大，乱码在世界中游荡……'}
            </p>
          </motion.div>
        )}

        <AnimatePresence>
          {messages.map((msg) => (
            <ChatBubble key={msg.id} msg={msg} emotion={currentEmotion} />
          ))}
        </AnimatePresence>

        {loading && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="flex items-center gap-2"
          >
            <div
              className="w-10 h-10 rounded-full flex items-center justify-center text-xl mr-2"
              style={{ backgroundColor: 'var(--realm-accent)', color: 'white' }}
            >
              {EMOTION_EXPRESSIONS[currentEmotion]}
            </div>
            <div className="dialogue-box px-4 py-3 flex items-center gap-2">
              <Loader2 size={16} className="animate-spin opacity-60" />
              <span style={{ fontSize: 13, opacity: 0.6 }}>正在思考...</span>
            </div>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* ── 选项按钮行 ──────────────────────────────────────────────────── */}
      {messages.length === 0 && (
        <div className="px-6 pb-2 flex flex-wrap gap-2">
          {options.map((opt) => (
            <button
              key={opt}
              onClick={() => handleSend(opt)}
              className="px-4 py-2 rounded-full text-sm font-medium border transition-all hover:scale-105"
              style={{
                borderColor: 'var(--card-border)',
                backgroundColor: 'var(--card-bg)',
                color: 'var(--realm-text)',
              }}
            >
              {opt}
            </button>
          ))}
          <button
            onClick={() => setShowGiftPanel(!showGiftPanel)}
            className="px-4 py-2 rounded-full text-sm font-medium border transition-all hover:scale-105 flex items-center gap-1"
            style={{
              borderColor: 'var(--realm-accent)',
              color: 'var(--realm-accent)',
              backgroundColor: 'transparent',
            }}
          >
            <Gift size={14} /> 赠送礼物
          </button>
        </div>
      )}

      {/* ── 礼物面板 ────────────────────────────────────────────────────── */}
      <AnimatePresence>
        {showGiftPanel && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="px-6 pb-2 overflow-hidden"
          >
            <div className="grid grid-cols-3 gap-2 p-3 rounded-xl" style={{ backgroundColor: 'var(--card-bg)', border: '1px solid var(--card-border)' }}>
              {Object.values(itemDefs).map((item) => (
                <button
                  key={item.id}
                  onClick={() => handleGift(item.id)}
                  className="flex flex-col items-center gap-1 p-2 rounded-lg hover:bg-white/10 transition-colors"
                >
                  <span style={{ fontSize: 24 }}>{item.emoji}</span>
                  <span style={{ fontSize: 11 }}>{item.name}</span>
                </button>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* ── 输入框 ──────────────────────────────────────────────────────── */}
      <div
        className="flex items-center gap-3 px-6 py-4 border-t"
        style={{ borderColor: 'var(--card-border)', backgroundColor: 'var(--card-bg)' }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSend()}
          placeholder={isScript ? '输入你想说的话...' : '在崩坏中低语...'}
          className="flex-1 px-4 py-3 rounded-full outline-none text-sm"
          style={{
            backgroundColor: 'var(--farm-bg)',
            color: 'var(--realm-text)',
            border: '1px solid var(--farm-grid-line)',
          }}
          disabled={loading}
        />
        <button
          onClick={() => handleSend()}
          disabled={loading || !input.trim()}
          className="w-11 h-11 rounded-full flex items-center justify-center shrink-0 transition-all hover:scale-110 disabled:opacity-40"
          style={{ backgroundColor: 'var(--realm-accent)', color: 'white' }}
        >
          <Send size={18} />
        </button>
      </div>
    </div>
  )
}
