/**
 * VeggieMatch – Live Camera Capture
 * Usage: initCamera(videoId, canvasId, captureBtn, previewId, hiddenInputId, retakeBtn)
 */
function initCamera(videoId, canvasId, captureBtnId, previewId, hiddenInputId, retakeBtnId) {
  const video     = document.getElementById(videoId);
  const canvas    = document.getElementById(canvasId);
  const captureBtn = document.getElementById(captureBtnId);
  const preview   = document.getElementById(previewId);
  const hidden    = document.getElementById(hiddenInputId);
  const retakeBtn = document.getElementById(retakeBtnId);

  let stream = null;

  async function startCamera() {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false });
      video.srcObject = stream;
      video.style.display = 'block';
      preview.style.display = 'none';
      captureBtn.style.display = 'inline-flex';
      retakeBtn.style.display = 'none';
      hidden.value = '';
    } catch (err) {
      alert('Camera access denied. Please allow camera access and try again.');
      console.error(err);
    }
  }

  captureBtn.addEventListener('click', () => {
    canvas.width  = video.videoWidth  || 640;
    canvas.height = video.videoHeight || 480;
    canvas.getContext('2d').drawImage(video, 0, 0);
    const dataUrl = canvas.toDataURL('image/jpeg', 0.85);
    hidden.value = dataUrl;

    // Show preview, hide video
    preview.src = dataUrl;
    preview.style.display = 'block';
    video.style.display = 'none';
    captureBtn.style.display = 'none';
    retakeBtn.style.display = 'inline-flex';

    // Stop stream to free camera
    if (stream) stream.getTracks().forEach(t => t.stop());
  });

  retakeBtn.addEventListener('click', () => startCamera());

  // Auto-start
  startCamera();
}
