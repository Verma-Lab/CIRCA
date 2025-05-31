// services/plotUtils.js
export function extractPlots(response) {
    // Handle different response formats
    const rawContent = typeof response === 'string' ? response : response.content || '';
    
    const plotRegex = /{{PLOT:(\w+)}}data:({.*?}){{ENDPLOT}}/gs;
    const plots = [];
    let cleanContent = rawContent;
  
    let match;
    while (match = plotRegex.exec(rawContent)) {
      try {
        plots.push({
          type: match[1],
          data: JSON.parse(match[2])
        });
        cleanContent = cleanContent.replace(match[0], '');
      } catch (e) {
        console.error('Error parsing plot:', e);
      }
    }
  
    return { 
      cleanContent: cleanContent.trim(),
      plots 
    };
  }