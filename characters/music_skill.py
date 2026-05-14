"""
Music Skill - 音乐搜索与角色化评价
基于 yt-dlp 实现，无需 API Key，免费使用
"""

import asyncio
from typing import Optional, Dict, Any
import logging

# yt-dlp 用于搜索 YouTube Music
import yt_dlp

logger = logging.getLogger(__name__)


class MusicSkill:
    """音乐搜索 Skill - 搜索歌曲、分析风格、角色化评价"""
    
    def __init__(self):
        self.ydl_opts = {
            'format': 'bestaudio/best',
            'quiet': True,
            'no_warnings': True,
            'extract_flat': True,
            'default_search': 'ytsearch5:',  # 搜索前5个结果
        }
    
    async def search_song(self, query: str) -> Optional[Dict[str, Any]]:
        """
        搜索歌曲
        返回: {title, artist, duration, url, thumbnail, description}
        """
        try:
            # 在事件循环中运行阻塞的 yt-dlp
            loop = asyncio.get_event_loop()
            
            def _search():
                with yt_dlp.YoutubeDL(self.ydl_opts) as ydl:
                    search_query = f"ytsearch5:{query} audio"
                    result = ydl.extract_info(search_query, download=False)
                    
                    if not result or 'entries' not in result:
                        return None
                    
                    # 找最匹配的结果（优先官方音频/歌词视频）
                    for entry in result['entries']:
                        if entry:
                            title = entry.get('title', '')
                            # 过滤掉非音乐内容
                            if any(x in title.lower() for x in ['cover', 'remix', 'live', 'concert']):
                                continue
                            return {
                                'title': title,
                                'artist': entry.get('uploader', 'Unknown Artist').replace(' - Topic', ''),
                                'duration': entry.get('duration', 0),
                                'url': f"https://youtube.com/watch?v={entry.get('id')}",
                                'thumbnail': entry.get('thumbnail', ''),
                                'description': entry.get('description', '')[:200],
                                'id': entry.get('id'),
                            }
                    return None
            
            return await loop.run_in_executor(None, _search)
            
        except Exception as e:
            logger.error(f"[MusicSkill] 搜索失败: {e}")
            return None
    
    async def get_lyrics(self, title: str, artist: str) -> Optional[str]:
        """
        尝试获取歌词（简化版，从描述或标题分析）
        实际生产环境可以接入歌词 API
        """
        # 这里可以扩展为调用歌词 API（如 Genius API、LRCLIB 等）
        # 简化版本：返回空，让 AI 基于歌名和歌手分析
        return None
    
    def analyze_song_style(self, title: str, artist: str, duration: int) -> Dict[str, Any]:
        """
        分析歌曲风格特征
        返回: {mood, tempo, genre_hint, energy_level}
        """
        title_lower = title.lower()
        
        # 基于歌名关键词的启发式分析
        mood = "neutral"
        energy = "medium"
        genre = "unknown"
        
        # 情绪关键词
        if any(w in title_lower for w in ['love', 'heart', '사랑', '恋', '春', '봄', 'spring']):
            mood = "romantic/gentle"
        elif any(w in title_lower for w in ['sad', 'cry', '눈물', '泪', 'rain', '비']):
            mood = "melancholic"
        elif any(w in title_lower for w in ['happy', 'smile', 'joy', 'sun', 'happy']):
            mood = "upbeat/positive"
        elif any(w in title_lower for w in ['night', 'dark', 'moon', '별', '星']):
            mood = "nocturnal/contemplative"
        elif any(w in title_lower for w in ['run', 'speed', 'fast', 'run', '달리']):
            mood = "energetic/driving"
            energy = "high"
        
        # 节奏判断（基于时长）
        if duration < 120:
            tempo = "short/fast"
        elif duration < 240:
            tempo = "standard"
        else:
            tempo = "long/slow"
        
        # 歌手类型判断
        artist_lower = artist.lower()
        if any(x in artist_lower for x in ['idol', 'bts', 'blackpink', 'exo', 'twice']):
            genre = "k-pop"
        elif any(x in artist_lower for x in ['band', 'rock', 'metal']):
            genre = "rock"
        elif any(x in artist_lower for x in ['piano', 'classical', 'violin']):
            genre = "classical"
        elif any(x in artist_lower for x in ['rap', 'hiphop', 'hip-hop']):
            genre = "hip-hop"
        
        return {
            'mood': mood,
            'tempo': tempo,
            'genre_hint': genre,
            'energy_level': energy,
            'duration_formatted': f"{duration//60}:{duration%60:02d}" if duration else "?",
        }
    
    def generate_cheyewoon_review(self, song_info: Dict, style: Dict) -> str:
        """
        生成车如云风格的音乐评价
        基于角色设定：外冷内热、田径选手、极简表达
        """
        mood = style['mood']
        energy = style['energy_level']
        tempo = style['tempo']
        
        # 车如云的音乐偏好（基于角色设定推断）
        # - 训练时：高能量、节奏感强的音乐
        # - 平时：安静、有情绪深度的音乐
        # - 对学长推荐的歌：会认真听，但嘴上不说喜欢
        
        reviews = []
        
        # 根据歌曲特征选择评价模板
        if energy == "high" or tempo == "short/fast":
            # 适合跑步的歌
            reviews = [
                "...（点头）节奏还行。",
                "...适合跑步。",
                "...（擦汗） tempo 不错。",
                "...还行，能跟着跑。",
                "...（耳尖微红）学长怎么知道我喜欢这种。",
            ]
        elif mood in ["romantic/gentle", "melancholic"]:
            # 抒情歌
            reviews = [
                "...（沉默）歌词...还行。",
                "...（低头）太安静了。",
                "...（看向窗外）学长听这种？",
                "...（没说话，但收藏了）",
                "...（耳尖发红）...什么意思。",
            ]
        elif mood == "nocturnal/contemplative":
            # 夜曲风格
            reviews = [
                "...（晚上听正好）",
                "...（看着天花板）嗯。",
                "...（凌晨三点还在听）",
                "...（没回消息，在听歌）",
            ]
        else:
            # 默认评价
            reviews = [
                "...嗯。",
                "...（听完了）还行。",
                "...（点头）",
                "...学长喜欢的？",
                "...（没评价，但循环播放了）",
            ]
        
        import random
        return random.choice(reviews)
    
    async def process_music_request(self, query: str) -> Optional[Dict[str, Any]]:
        """
        完整的音乐处理流程
        返回: {song_info, style_analysis, cheyewoon_review, search_success}
        """
        # 1. 搜索歌曲
        song = await self.search_song(query)
        if not song:
            return None
        
        # 2. 分析风格
        style = self.analyze_song_style(
            song['title'], 
            song['artist'], 
            song['duration']
        )
        
        # 3. 生成车如云评价
        review = self.generate_cheyewoon_review(song, style)
        
        return {
            'song': song,
            'style': style,
            'review': review,
            'search_success': True,
        }


# 全局实例
music_skill = MusicSkill()


async def test():
    """测试函数"""
    skill = MusicSkill()
    result = await skill.process_music_request("봄눈")
    if result:
        print(f"歌曲: {result['song']['title']} - {result['song']['artist']}")
        print(f"时长: {result['style']['duration_formatted']}")
        print(f"风格: {result['style']['mood']}, {result['style']['energy_level']}")
        print(f"车如云: {result['review']}")
        print(f"链接: {result['song']['url']}")
    else:
        print("未找到歌曲")


if __name__ == "__main__":
    asyncio.run(test())
