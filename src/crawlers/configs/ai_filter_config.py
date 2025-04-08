# AI相關常數和設定
from typing import Set

# AI相關關鍵字集合，用於篩選文章
AI_KEYWORDS: Set[str] = {
    # 一般AI技術名詞
    'ai', '人工智能', '人工智慧', '機器學習', 'machine learning', 'ml', 'deep learning', '深度學習',
    '神經網絡', '神經網路', 'neural network', '大型語言模型', 'llm', 'large language model',
    '生成式ai', '生成式人工智慧', 'generative ai', '人工智能技術', 'nlp', '自然語言處理',
    'chatgpt', 'claude', 'gemini', 'gpt', 'openai', 'anthropic',
    
    # AI應用
    '智能助理', '智慧助理', 'ai助理', '語音助手', 'ai機器人', 'ai模型', '預測模型',
    '推薦系統', '圖像識別', '圖像辨識', '人臉辨識', '人臉識別', '語音識別', '語音辨識',
    '機器翻譯', 'ai翻譯', '自動駕駛', '無人駕駛', '智能推薦', '智慧推薦',
    
    # 相關技術
    '強化學習', 'reinforcement learning', '監督式學習', '無監督學習', '半監督學習',
    '遷移學習', 'transfer learning', '聯邦學習', 'federated learning',
    'transformer', 'diffusion', '擴散模型', '注意力機制', 'attention mechanism',
    '向量資料庫', 'vector database', '向量嵌入', 'embedding',
    
    # 相關議題
    '人工智慧倫理', 'ai倫理', 'ai ethics', '演算法偏見', 'algorithmic bias',
    'ai監管', 'ai regulation', 'ai政策', 'ai policy', 'ai發展',
    '大模型', 'foundation model', '基礎模型'
}

# AI相關的分類名稱
AI_CATEGORIES: Set[str] = {
    'ai', 'artificial intelligence', '人工智能', '人工智慧', '機器學習', 'machine learning',
    'deep learning', '深度學習', '大語言模型', 'llm', '生成式ai'
}

# 優先級高的關鍵字 - 這些出現即可判定為AI相關
HIGH_PRIORITY_KEYWORDS: Set[str] = {
    'chatgpt', 'gpt-4', 'gpt-3', 'claude', 'gemini', 'llama', 'midjourney', 'stable diffusion',
    '大語言模型', 'llm', '生成式ai', 'generative ai', '人工智慧'
}

def register_additional_keywords(*keywords: str) -> None:
    """註冊額外的AI關鍵字"""
    global AI_KEYWORDS
    for keyword in keywords:
        AI_KEYWORDS.add(keyword.lower())

def register_additional_categories(*categories: str) -> None:
    """註冊額外的AI分類"""
    global AI_CATEGORIES
    for category in categories:
        AI_CATEGORIES.add(category.lower())
