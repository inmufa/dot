(function(){
var send=function(k,m){try{parent.postMessage({dotArtifact:1,kind:k,message:String(m).slice(0,1000)},"*")}catch(e){}};
window.addEventListener("error",function(e){send("error",(e.message||"error")+(e.lineno?" (line "+e.lineno+")":""))});
window.addEventListener("unhandledrejection",function(e){send("error","Unhandled rejection: "+((e.reason&&e.reason.message)||e.reason))});
["error","warn"].forEach(function(l){var o=console[l];console[l]=function(){send(l,[].map.call(arguments,String).join(" "));o.apply(console,arguments)}});
document.addEventListener("securitypolicyviolation",function(e){send("error","Blocked by the sandbox policy ("+e.violatedDirective+") "+(e.blockedURI||""))});
})();
