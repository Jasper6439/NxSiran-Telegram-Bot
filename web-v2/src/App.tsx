// ═══════════════════════════════════════════════════════════════════════════
// 恋爱至上主义区域 - 主应用
// ═══════════════════════════════════════════════════════════════════════════
import { RouterProvider } from 'react-router-dom';
import { router } from './routes';

function App() {
  return <RouterProvider router={router} />;
}

export default App;
