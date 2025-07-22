'use client';

import React, { useState } from 'react';
import { Package as PackageBox } from 'lucide-react';
import { Button } from '@/components/ui/button';
import FileUploader from '@/components/transcribe/FileUploader';
import AudioRecorder from '@/components/transcribe/AudioRecorder';
import TranscriptDisplay from '@/components/transcribe/TranscriptDisplay';
import { useToast } from '@/hooks/use-toast';

export default function Home() {
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [isTranscribing, setIsTranscribing] = useState(false);
  const [transcript, setTranscript] = useState<{shipper: string[], customer: string[]} | null>(null);
  const [line, setLine] = useState<string>("");
  const { toast } = useToast();

  const handleFileSelect = (file: File) => {
    setSelectedFile(file);
  };

  const uploadRecordingToServer = async (audioBlob: Blob) => {
    try {
      const file = new File([audioBlob], `recording-${Date.now()}.wav`, { type: 'audio/wav' });
      
      const formData = new FormData();
      formData.append('file', file);
      
      const response = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Upload failed');
      }
      
      const result = await response.json();
      
      toast({
        title: "Recording uploaded",
        description: `Recording saved as ${result.filename} in tmp directory.`,
        variant: "success",
      });
      
      return file;
    } catch (error) {
      console.error('Upload error:', error);
      toast({
        title: "Upload failed",
        description: error instanceof Error ? error.message : "Failed to upload recording to server.",
        variant: "destructive",
      });
      throw error;
    }
  };

  const handleRecordingComplete = async (audioBlob: Blob) => {
    try {
      const file = await uploadRecordingToServer(audioBlob);
      setSelectedFile(file);
    } catch (error) {
      console.error('Failed to upload recording:', error);
    }
  };

  const handleTranscribe = async () => {
    if (!selectedFile) {
      toast({
        title: "No file selected",
        description: "Please upload a file or record audio first.",
        variant: "destructive",
      });
      return;
    }

    try {
      setIsTranscribing(true);
      
      // Gọi API transcribe để xử lý file trong tmp
      const response = await fetch('/api/transcribe', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.error || 'Failed to transcribe audio');
      }
      
      const data = await response.json();
      
      if (data.success && data.text) {
        console.log('Transcription result:', data);
        setLine(data.text);
        setTranscript(null); // Reset transcript nếu có
      } else {
        throw new Error(data.error || 'Invalid response from transcription service');
      }

      toast({
        title: "Transcription complete",
        description: "Your audio has been transcribed and processed.",
        variant: "success",
      });
    } catch (error) {
      console.error('Error transcribing:', error);
      toast({
        title: "Transcription failed",
        description: error instanceof Error ? error.message : "There was an error transcribing your audio.",
        variant: "destructive",
      });
    } finally {
      setIsTranscribing(false);
    }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="flex items-center mb-8">
        <PackageBox className="h-8 w-8 mr-2" />
        <h1 className="text-3xl font-bold">DeliverTalk</h1>
      </div>
      
      <div className="space-y-6">
        <FileUploader onFileSelect={handleFileSelect} />
        
        <div className="flex justify-center">
          <div className="text-sm text-gray-500">or</div>
        </div>
        
        <AudioRecorder onRecordingComplete={handleRecordingComplete} />
        
        <div className="flex justify-end">
          <Button 
            onClick={handleTranscribe}
            disabled={!selectedFile || isTranscribing}
            className="px-8"
          >
            Transcribe
            {isTranscribing && (
              <span className="ml-2">
                <span className="animate-spin inline-block h-4 w-4 border-2 border-current border-t-transparent rounded-full"></span>
              </span>
            )}
          </Button>
        </div>
        
        <TranscriptDisplay 
          transcript={transcript} 
          singleLine={line}
          isLoading={isTranscribing} 
        />
      </div>
    </div>
  );
}