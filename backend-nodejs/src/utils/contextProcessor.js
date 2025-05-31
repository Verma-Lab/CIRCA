// contextProcessor.js
export class ContextProcessor {
    static summarizeContent(content, maxLength = 500) {
      if (!content) return '';
      if (content.length <= maxLength) return content;
      
      // Split into sentences
      const sentences = content.split(/(?<=[.!?])\s+/);
      let summary = '';
      
      for (const sentence of sentences) {
        if ((summary + sentence).length > maxLength) break;
        summary += (summary ? ' ' : '') + sentence;
      }
      
      return summary;
    }
  
    static processContext(context) {
      return context.map(item => {
        if (item.role !== 'system') return item;
  
        // Process system messages (like document content)
        const summarizedContent = this.summarizeContent(item.content);
        return {
          ...item,
          content: summarizedContent,
          originalLength: item.content.length
        };
      });
    }
  }