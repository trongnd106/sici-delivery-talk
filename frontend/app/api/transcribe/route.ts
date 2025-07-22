import { NextResponse } from 'next/server';

export async function POST(request: Request) {
  try {
    console.log('Bắt đầu xử lý transcription...');
    
    // Gọi backend để xử lý file mới nhất trong tmp
    const backendUrl = process.env.BACKEND_URL || 'http://localhost:5000';
    const response = await fetch(`${backendUrl}/process_audio`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.error || 'Backend processing failed');
    }
    
    const result = await response.json();
    
    if (!result.success) {
      throw new Error(result.error || 'Processing failed');
    }
    
    console.log('Transcription completed:', result);
    
    // Trả về kết quả dạng text đơn giản
    let transcriptText = "";
    if (result.transcriptions && result.transcriptions.length > 0) {
      for (const trans of result.transcriptions) {
        transcriptText += `${trans.speaker}: ${trans.text}\n`;
      }
    }
    
    return NextResponse.json({
      success: true,
      text: transcriptText.trim(),
      result: result
    }, { status: 200 });
    
  } catch (error) {
    console.error('Error processing transcription:', error);
    return NextResponse.json(
      { 
        success: false,
        error: error instanceof Error ? error.message : 'Failed to process transcription' 
      },
      { status: 500 }
    );
  }
}