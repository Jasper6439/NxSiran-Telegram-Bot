import { Link, useLocation } from 'react-router-dom';

export function BottomNav() {
  const location = useLocation();
  
  const navItems = [
    { path: '/', label: '首页', icon: '🏠' },
    { path: '/game', label: '农场', icon: '🌱' },
    { path: '/chat', label: '聊天', icon: '💬' },
    { path: '/settings', label: '设置', icon: '⚙️' },
  ];

  return (
    <nav className="fixed bottom-0 left-0 right-0 bg-white/90 backdrop-blur-md border-t border-gray-200">
      <div className="flex justify-around items-center h-16 max-w-lg mx-auto">
        {navItems.map((item) => {
          const isActive = location.pathname === item.path;
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex flex-col items-center justify-center w-16 h-14 rounded-xl transition-colors ${
                isActive ? 'text-brand-500' : 'text-gray-400'
              }`}
            >
              <span className="text-xl">{item.icon}</span>
              <span className="text-xs font-medium mt-0.5">{item.label}</span>
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
