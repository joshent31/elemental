package com.elementalfixtures.mobile;

import android.Manifest;
import android.annotation.SuppressLint;
import android.app.Activity;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.graphics.Bitmap;
import android.graphics.Color;
import android.net.Uri;
import android.os.Bundle;
import android.os.SystemClock;
import android.view.Gravity;
import android.view.View;
import android.view.WindowManager;
import android.webkit.CookieManager;
import android.webkit.JavascriptInterface;
import android.webkit.PermissionRequest;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.ProgressBar;
import android.widget.Toast;

import com.google.zxing.ResultPoint;
import com.journeyapps.barcodescanner.BarcodeCallback;
import com.journeyapps.barcodescanner.BarcodeResult;
import com.journeyapps.barcodescanner.DecoratedBarcodeView;

import org.json.JSONObject;

import java.util.Arrays;
import java.util.List;

public class MainActivity extends Activity {
    private static final int CAMERA_PERMISSION_REQUEST = 1001;

    private WebView webView;
    private ProgressBar progressBar;
    private DecoratedBarcodeView nativeScanner;
    private Button closeScannerButton;
    private PermissionRequest pendingWebCameraRequest;
    private boolean nativeScannerPermissionPending;
    private String lastNativeScan;
    private long lastNativeScanAt;
    private Uri trustedOrigin;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        trustedOrigin = Uri.parse(BuildConfig.BASE_URL);

        if ("/gate-scan".equals(BuildConfig.START_PATH)) {
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON);
        }

        FrameLayout root = new FrameLayout(this);
        webView = new WebView(this);
        progressBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);

        root.addView(webView, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));
        FrameLayout.LayoutParams progressLayout = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                8
        );
        root.addView(progressBar, progressLayout);
        configureNativeScanner(root);
        setContentView(root);

        configureWebView();
        if (savedInstanceState == null) {
            webView.loadUrl(joinUrl(BuildConfig.BASE_URL, BuildConfig.START_PATH));
        } else {
            webView.restoreState(savedInstanceState);
        }
    }

    @SuppressLint("SetJavaScriptEnabled")
    private void configureWebView() {
        WebSettings settings = webView.getSettings();
        settings.setJavaScriptEnabled(true);
        settings.setDomStorageEnabled(true);
        settings.setDatabaseEnabled(true);
        settings.setMediaPlaybackRequiresUserGesture(false);
        settings.setAllowFileAccess(false);
        settings.setAllowContentAccess(false);
        settings.setUserAgentString(settings.getUserAgentString() + " ElementalMobile/1.0");

        CookieManager cookieManager = CookieManager.getInstance();
        cookieManager.setAcceptCookie(true);
        cookieManager.setAcceptThirdPartyCookies(webView, false);
        webView.addJavascriptInterface(new ScannerBridge(), "ElementalAndroid");

        WebView.setWebContentsDebuggingEnabled(BuildConfig.DEBUG);
        webView.setWebViewClient(new WebViewClient() {
            @Override
            public void onPageStarted(WebView view, String url, Bitmap favicon) {
                progressBar.setVisibility(View.VISIBLE);
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                progressBar.setVisibility(View.GONE);
                CookieManager.getInstance().flush();
                installNativeScannerBridge();
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest request) {
                return openExternallyIfNeeded(request.getUrl());
            }

            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String url) {
                return openExternallyIfNeeded(Uri.parse(url));
            }
        });

        webView.setWebChromeClient(new WebChromeClient() {
            @Override
            public void onProgressChanged(WebView view, int newProgress) {
                progressBar.setProgress(newProgress);
            }

            @Override
            public void onPermissionRequest(PermissionRequest request) {
                runOnUiThread(() -> handleWebPermissionRequest(request));
            }

            @Override
            public void onPermissionRequestCanceled(PermissionRequest request) {
                if (request == pendingWebCameraRequest) {
                    pendingWebCameraRequest = null;
                }
            }
        });
    }

    private void configureNativeScanner(FrameLayout root) {
        nativeScanner = new DecoratedBarcodeView(this);
        nativeScanner.setStatusText("Point the camera at a QR code");
        nativeScanner.setVisibility(View.GONE);
        root.addView(nativeScanner, new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.MATCH_PARENT,
                FrameLayout.LayoutParams.MATCH_PARENT
        ));

        closeScannerButton = new Button(this);
        closeScannerButton.setText(R.string.close_camera);
        closeScannerButton.setTextColor(Color.BLACK);
        closeScannerButton.setBackgroundColor(Color.WHITE);
        closeScannerButton.setVisibility(View.GONE);
        closeScannerButton.setOnClickListener(view -> {
            hideNativeScanner();
            webView.evaluateJavascript(
                    "var b=document.getElementById('start-scan-gate');if(b){b.style.display='block';}",
                    null
            );
        });
        FrameLayout.LayoutParams closeLayout = new FrameLayout.LayoutParams(
                FrameLayout.LayoutParams.WRAP_CONTENT,
                FrameLayout.LayoutParams.WRAP_CONTENT,
                Gravity.BOTTOM | Gravity.CENTER_HORIZONTAL
        );
        closeLayout.bottomMargin = 40;
        root.addView(closeScannerButton, closeLayout);

        nativeScanner.decodeContinuous(new BarcodeCallback() {
            @Override
            public void barcodeResult(BarcodeResult result) {
                deliverNativeScan(result == null ? null : result.getText());
            }

            @Override
            public void possibleResultPoints(List<ResultPoint> resultPoints) {
                // The viewfinder renders these points itself.
            }
        });
    }

    private void installNativeScannerBridge() {
        if (!isCurrentPageTrusted()) {
            return;
        }
        String script = "(function patchElementalScanner(attempt){"
                + "if(window.__elementalNativeScannerInstalled){return;}"
                + "if(!window.Html5Qrcode||!window.ElementalAndroid){"
                + "if(attempt<50){setTimeout(function(){patchElementalScanner(attempt+1);},100);}return;}"
                + "window.__elementalNativeScannerInstalled=true;"
                + "window.Html5Qrcode.prototype.start=function(camera,config,onSuccess,onError){"
                + "window.__elementalNativeScanSuccess=onSuccess;"
                + "window.__elementalNativeScanError=onError;"
                + "window.ElementalAndroid.startScanner();return Promise.resolve();};"
                + "window.Html5Qrcode.prototype.stop=function(){"
                + "window.ElementalAndroid.stopScanner();return Promise.resolve();};"
                + "window.__elementalDeliverNativeScan=function(value){"
                + "if(typeof window.__elementalNativeScanSuccess==='function'){"
                + "window.__elementalNativeScanSuccess(value,{decodedText:value});}};"
                + "})(0);";
        webView.evaluateJavascript(script, null);
    }

    private final class ScannerBridge {
        @JavascriptInterface
        public void startScanner() {
            runOnUiThread(() -> {
                if (isCurrentPageTrusted()) {
                    requestNativeScanner();
                }
            });
        }

        @JavascriptInterface
        public void stopScanner() {
            runOnUiThread(() -> {
                if (isCurrentPageTrusted()) {
                    hideNativeScanner();
                }
            });
        }
    }

    private void requestNativeScanner() {
        if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            showNativeScanner();
            return;
        }
        nativeScannerPermissionPending = true;
        requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION_REQUEST);
    }

    private void showNativeScanner() {
        nativeScannerPermissionPending = false;
        nativeScanner.setVisibility(View.VISIBLE);
        closeScannerButton.setVisibility(View.VISIBLE);
        nativeScanner.resume();
    }

    private void hideNativeScanner() {
        nativeScannerPermissionPending = false;
        nativeScanner.pause();
        nativeScanner.setVisibility(View.GONE);
        closeScannerButton.setVisibility(View.GONE);
    }

    private void deliverNativeScan(String value) {
        if (value == null || value.isEmpty()) {
            return;
        }
        long now = SystemClock.elapsedRealtime();
        if (value.equals(lastNativeScan) && now - lastNativeScanAt < 1500) {
            return;
        }
        lastNativeScan = value;
        lastNativeScanAt = now;
        webView.evaluateJavascript(
                "window.__elementalDeliverNativeScan(" + JSONObject.quote(value) + ");",
                null
        );
    }

    private void handleWebPermissionRequest(PermissionRequest request) {
        boolean wantsOnlyCamera = Arrays.equals(
                request.getResources(),
                new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE}
        );
        if (!isTrustedOrigin(request.getOrigin()) || !wantsOnlyCamera) {
            request.deny();
            return;
        }
        if (checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            request.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            return;
        }
        pendingWebCameraRequest = request;
        requestPermissions(new String[]{Manifest.permission.CAMERA}, CAMERA_PERMISSION_REQUEST);
    }

    @Override
    public void onRequestPermissionsResult(int requestCode, String[] permissions, int[] grantResults) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults);
        if (requestCode != CAMERA_PERMISSION_REQUEST) {
            return;
        }
        boolean granted = grantResults.length > 0 && grantResults[0] == PackageManager.PERMISSION_GRANTED;
        if (nativeScannerPermissionPending) {
            if (granted) {
                showNativeScanner();
            } else {
                nativeScannerPermissionPending = false;
            }
        }
        if (pendingWebCameraRequest != null) {
            PermissionRequest request = pendingWebCameraRequest;
            pendingWebCameraRequest = null;
            if (granted) {
                request.grant(new String[]{PermissionRequest.RESOURCE_VIDEO_CAPTURE});
            } else {
                request.deny();
            }
        }
        if (!granted) {
            Toast.makeText(this, "Camera permission is required to scan QR codes.", Toast.LENGTH_LONG).show();
        }
    }

    private boolean openExternallyIfNeeded(Uri target) {
        if (isTrustedOrigin(target) || "about".equalsIgnoreCase(target.getScheme())) {
            return false;
        }
        try {
            startActivity(new Intent(Intent.ACTION_VIEW, target));
        } catch (Exception error) {
            Toast.makeText(this, "Unable to open this link.", Toast.LENGTH_SHORT).show();
        }
        return true;
    }

    private boolean isTrustedOrigin(Uri target) {
        if (target == null || trustedOrigin == null) {
            return false;
        }
        return equalsIgnoreCase(trustedOrigin.getScheme(), target.getScheme())
                && equalsIgnoreCase(trustedOrigin.getHost(), target.getHost())
                && effectivePort(trustedOrigin) == effectivePort(target);
    }

    private boolean isCurrentPageTrusted() {
        String currentUrl = webView.getUrl();
        return currentUrl != null && isTrustedOrigin(Uri.parse(currentUrl));
    }

    private static boolean equalsIgnoreCase(String left, String right) {
        return left != null && right != null && left.equalsIgnoreCase(right);
    }

    private static int effectivePort(Uri uri) {
        if (uri.getPort() != -1) {
            return uri.getPort();
        }
        return "https".equalsIgnoreCase(uri.getScheme()) ? 443 : 80;
    }

    private static String joinUrl(String baseUrl, String path) {
        String base = baseUrl.endsWith("/") ? baseUrl.substring(0, baseUrl.length() - 1) : baseUrl;
        String suffix = path.startsWith("/") ? path : "/" + path;
        return base + suffix;
    }

    @Override
    protected void onSaveInstanceState(Bundle outState) {
        webView.saveState(outState);
        super.onSaveInstanceState(outState);
    }

    @Override
    public void onBackPressed() {
        if (nativeScanner.getVisibility() == View.VISIBLE) {
            hideNativeScanner();
        } else if (webView.canGoBack()) {
            webView.goBack();
        } else {
            super.onBackPressed();
        }
    }

    @Override
    protected void onPause() {
        if (nativeScanner.getVisibility() == View.VISIBLE) {
            nativeScanner.pause();
        }
        super.onPause();
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (nativeScanner.getVisibility() == View.VISIBLE
                && checkSelfPermission(Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) {
            nativeScanner.resume();
        }
    }

    @Override
    protected void onDestroy() {
        nativeScanner.pause();
        if (pendingWebCameraRequest != null) {
            pendingWebCameraRequest.deny();
            pendingWebCameraRequest = null;
        }
        webView.destroy();
        super.onDestroy();
    }
}
