import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { motion } from 'framer-motion'
import { Gamepad2, MessageCircle, Sparkles } from 'lucide-react'

// ─────────────────────────────────────────────────────────────────────────────
// 角色数据
// ─────────────────────────────────────────────────────────────────────────────

interface Character {
  id: string
  name: string
  avatar?: string
  description?: string
  color?: string
}

// ─────────────────────────────────────────────────────────────────────────────
// 组件
// ─────────────────────────────────────────────────────────────────────────────

export default function WorldPage() {
  const navigate = useNavigate()
  const [characters, setCharacters] = useState<Character[]>([])
  const [selectedChar, setSelectedChar] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)

  useEffect(() => {
    const fetchCharacters = async () => {
      try {
        const token = localStorage.getItem('ls_token')
        if (!token) { setLoading(false); return }

        const res = await fetch('/api/characters', {
          headers: { Authorization: `Bearer ${token}` },
        })
        if (res.ok) {
          const data = await res.json()
          setCharacters(data.characters || [])
        } else {
          setError(true)
        }
      } catch {
        setError(true)
      }
      setLoading(false)
    }
    fetchCharacters()
  }, [])

  const handleSelectCharacter = (charId: string) => {
    setSelectedChar(charId)
    // 导航到游戏聊天界面，携带角色ID
    navigate(`/game?character=${charId}`)
  }

  return (
    <div className="ios-page">
      <div className="ios-safe-top" />

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="ios-navbar" style={{ padding: '8px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <motion.button
            whileTap={{ scale: 0.9 }}
            onClick={() => navigate('/game')}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              padding: '6px 14px',
              borderRadius: 20,
              background: 'linear-gradient(135deg, var(--ios-purple), var(--ios-blue))',
              color: '#fff',
              fontSize: 13,
              fontWeight: 600,
              border: 'none',
              cursor: 'pointer',
              boxShadow: '0 2px 8px rgba(139,92,246,0.3)',
            }}
          >
            <Gamepad2 size={16} />
            进入游戏
          </motion.button>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles size={18} style={{ color: 'var(--ios-purple)' }} />
          <span style={{ fontSize: 17, fontWeight: 600, color: 'var(--realm-text)' }}>
            世界
          </span>
        </div>
      </div>

      {/* ── 角色列表 ────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'auto', padding: '16px' }}>
        {loading ? (
          <div style={{ textAlign: 'center', padding: 40, color: 'var(--ios-gray)' }}>
            加载中...
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            <p style={{
              fontSize: 13,
              color: 'var(--ios-gray)',
              padding: '0 4px',
            }}>
              选择一个角色开始聊天
            </p>
            {characters.map((char, i) => (
              <motion.div
                key={char.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: i * 0.06 }}
                whileTap={{ scale: 0.97 }}
                onClick={() => handleSelectCharacter(char.id)}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 14,
                  padding: '16px',
                  borderRadius: 16,
                  background: selectedChar === char.id
                    ? 'rgba(139, 92, 246, 0.08)'
                    : 'var(--ios-bg-secondary)',
                  border: selectedChar === char.id
                    ? '1px solid var(--ios-purple)'
                    : '1px solid var(--ios-border)',
                  cursor: 'pointer',
                }}
              >
                {/* 头像 */}
                <div
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: '50%',
                    background: `linear-gradient(135deg, ${char.color || '#8B5CF6'}, ${char.color || '#8B5CF6'}dd)`,
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontSize: 22,
                    color: '#fff',
                    fontWeight: 700,
                    flexShrink: 0,
                  }}
                >
                  {char.name[0]}
                </div>

                {/* 信息 */}
                <div style={{ flex: 1 }}>
                  <div style={{ fontSize: 16, fontWeight: 600, color: 'var(--realm-text)' }}>
                    {char.name}
                  </div>
                  <div style={{ fontSize: 13, color: 'var(--ios-gray)', marginTop: 2 }}>
                    {char.description || '点击开始对话'}
                  </div>
                </div>

                {/* 箭头 */}
                <MessageCircle size={20} style={{ color: 'var(--ios-gray)', flexShrink: 0 }} />
              </motion.div>
            ))}

            {characters.length === 0 && !loading && (
              <div style={{
                textAlign: 'center',
                padding: 40,
                color: 'var(--ios-gray)',
                fontSize: 14,
              }}>
                {error ? '加载角色失败，请稍后重试' : '暂无可用角色'}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
