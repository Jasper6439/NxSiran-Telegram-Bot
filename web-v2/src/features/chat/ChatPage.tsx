import { useState, useRef, useEffect } from 'react';
import { Send, User, Settings, Sparkles, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/ui/avatar';
import { ScrollArea } from '@/components/ui/scroll-area';
import { BottomNav } from '@/components/BottomNav';
import { useNavigate } from 'react-router-dom';

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  isStreaming?: boolean;
}

interface SSEEvent {
  type: 'token' | 'done' | 'error';
  content: string;
}

export function ChatPage() {
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [showSelfie, setShowSelfie] = useState(false);
  const selfieImage = useState<string | null>(null)[0];
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Check login status
  useEffect(() => {
    const checkLogin = () => {
      const sessionToken = localStorage.getItem('session_token');
      const apiToken = localStorage.getItem('api_token');
      setIsLoggedIn(!!(sessionToken || apiToken));
    };

    checkLogin();

    // Listen for login/logout events from other tabs/pages
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'session_token' || e.key === 'api_token') {
        checkLogin();
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, []);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);

    // Create placeholder for assistant response
    const assistantMessageId = (Date.now() + 1).toString();
    const assistantMessage: Message = {
      id: assistantMessageId,
      role: 'assistant',
      content: '',
      timestamp: new Date(),
      isStreaming: true,
    };
    setMessages(prev => [...prev, assistantMessage]);

    // Get auth token
    const sessionToken = localStorage.getItem('session_token');
    const apiToken = localStorage.getItem('api_token');
    const token = sessionToken || apiToken;

    if (!token) {
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, content: '请先登录后再聊天。', isStreaming: false }
            : msg
        )
      );
      setIsLoading(false);
      return;
    }

    try {
      // Use SSE streaming
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          message: userMessage.content,
          character_id: 'chayewoon',
          stream: true,
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      const reader = response.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('No response body');
      }

      let fullContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;

          const data = line.slice(6);
          if (data === '[DONE]') continue;

          try {
            const event: SSEEvent = JSON.parse(data);

            if (event.type === 'token') {
              fullContent += event.content;
              setMessages(prev =>
                prev.map(msg =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: fullContent }
                    : msg
                )
              );
            } else if (event.type === 'done') {
              setMessages(prev =>
                prev.map(msg =>
                  msg.id === assistantMessageId
                    ? { ...msg, isStreaming: false }
                    : msg
                )
              );
            } else if (event.type === 'error') {
              setMessages(prev =>
                prev.map(msg =>
                  msg.id === assistantMessageId
                    ? { ...msg, content: `错误: ${event.content}`, isStreaming: false }
                    : msg
                )
              );
            }
          } catch {
            console.error('Failed to parse SSE event');
          }
        }
      }

      // Check for selfie in the response (non-streaming mode only)
      // For streaming, selfie would need separate handling
    } catch (error) {
      console.error('Chat error:', error);
      setMessages(prev =>
        prev.map(msg =>
          msg.id === assistantMessageId
            ? { ...msg, content: '抱歉，连接出错了。请稍后再试。', isStreaming: false }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-pink-50 to-purple-50 dark:from-gray-900 dark:to-gray-800 flex flex-col">
      {/* Header */}
      <header className="bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-b border-pink-100 dark:border-gray-700 sticky top-0 z-10">
        <div className="max-w-2xl mx-auto px-4 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Avatar className="h-9 w-9 ring-2 ring-pink-200 dark:ring-pink-800">
              <AvatarImage src="/icons/chayewoon.jpg" alt="车如云" />
              <AvatarFallback className="bg-pink-100 dark:bg-pink-900 text-pink-600 dark:text-pink-300 text-sm">
                车
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="font-semibold text-gray-900 dark:text-gray-100 text-sm">车如云</h1>
              <p className="text-xs text-gray-500 dark:text-gray-400 flex items-center gap-1">
                <span className="w-1.5 h-1.5 bg-green-500 rounded-full"></span>
                在线
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-gray-600 dark:text-gray-300 hover:text-pink-600 dark:hover:text-pink-400"
              onClick={() => navigate('/settings')}
            >
              <Settings className="h-4 w-4" />
            </Button>
            {messages.length > 0 && (
              <Button
                variant="ghost"
                size="icon"
                className="h-8 w-8 text-gray-600 dark:text-gray-300 hover:text-pink-600 dark:hover:text-pink-400"
                onClick={clearChat}
              >
                <X className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      </header>

      {/* Messages */}
      <ScrollArea className="flex-1">
        <div className="max-w-2xl mx-auto px-4 py-4 space-y-4">
          {messages.length === 0 ? (
            <div className="text-center py-12">
              <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-pink-100 dark:bg-pink-900/30 flex items-center justify-center">
                <Sparkles className="w-8 h-8 text-pink-500 dark:text-pink-400" />
              </div>
              <h2 className="text-lg font-medium text-gray-900 dark:text-gray-100 mb-2">
                开始和车如云聊天吧
              </h2>
              <p className="text-sm text-gray-500 dark:text-gray-400 max-w-sm mx-auto">
                她是《恋爱至上主义区域》中的傲娇女主角，试着和她聊聊看？
              </p>
            </div>
          ) : (
            messages.map((message) => (
              <div
                key={message.id}
                className={`flex gap-3 ${
                  message.role === 'user' ? 'flex-row-reverse' : ''
                }`}
              >
                <Avatar className={`h-8 w-8 shrink-0 ${
                  message.role === 'user'
                    ? 'bg-blue-100 dark:bg-blue-900'
                    : 'ring-2 ring-pink-200 dark:ring-pink-800'
                }`}>
                  {message.role === 'assistant' ? (
                    <>
                      <AvatarImage src="/icons/chayewoon.jpg" alt="车如云" />
                      <AvatarFallback className="bg-pink-100 dark:bg-pink-900 text-pink-600 dark:text-pink-300 text-xs">
                        车
                      </AvatarFallback>
                    </>
                  ) : (
                    <AvatarFallback className="bg-blue-100 dark:bg-blue-900 text-blue-600 dark:text-blue-300 text-xs">
                      <User className="h-4 w-4" />
                    </AvatarFallback>
                  )}
                </Avatar>
                <div
                  className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
                    message.role === 'user'
                      ? 'bg-blue-500 text-white rounded-br-md'
                      : 'bg-white dark:bg-gray-800 text-gray-800 dark:text-gray-100 border border-gray-100 dark:border-gray-700 rounded-bl-md shadow-sm'
                  }`}
                >
                  {message.content || '\u00A0'}
                  {message.isStreaming && (
                    <span className="inline-flex ml-1">
                      <span className="animate-bounce">.</span>
                      <span className="animate-bounce" style={{ animationDelay: '0.2s' }}>.</span>
                      <span className="animate-bounce" style={{ animationDelay: '0.4s' }}>.</span>
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
          <div ref={messagesEndRef} />
        </div>
      </ScrollArea>

      {/* Selfie Modal */}
      {showSelfie && selfieImage && (
        <div
          className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4"
          onClick={() => setShowSelfie(false)}
        >
          <div className="bg-white dark:bg-gray-800 rounded-lg overflow-hidden max-w-sm w-full">
            <img
              src={`data:image/jpeg;base64,${selfieImage}`}
              alt="车如云的自拍"
              className="w-full aspect-square object-cover"
            />
            <div className="p-3 text-center">
              <p className="text-sm text-gray-600 dark:text-gray-300">...给你。</p>
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="bg-white/80 dark:bg-gray-900/80 backdrop-blur-md border-t border-pink-100 dark:border-gray-700">
        <div className="max-w-2xl mx-auto px-4 py-3">
          {!isLoggedIn ? (
            <div className="flex items-center justify-center gap-2 py-2 text-sm text-gray-500 dark:text-gray-400">
              <span>请先</span>
              <Button
                variant="link"
                className="h-auto p-0 text-pink-600 dark:text-pink-400"
                onClick={() => navigate('/settings')}
              >
                登录账号
              </Button>
              <span>开始聊天</span>
            </div>
          ) : (
            <div className="flex gap-2">
              <Input
                value={input}
                onChange={(e: React.ChangeEvent<HTMLInputElement>) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="输入消息..."
                disabled={isLoading}
                className="flex-1 bg-white dark:bg-gray-800 border-gray-200 dark:border-gray-700 focus-visible:ring-pink-500 dark:text-gray-100"
              />
              <Button
                onClick={handleSend}
                disabled={!input.trim() || isLoading}
                className="bg-pink-500 hover:bg-pink-600 dark:bg-pink-600 dark:hover:bg-pink-700 text-white px-4"
              >
                {isLoading ? (
                  <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                ) : (
                  <Send className="w-4 h-4" />
                )}
              </Button>
            </div>
          )}
        </div>
      </div>

      <BottomNav />
    </div>
  );
}

// Default export for route compatibility
export default ChatPage;
