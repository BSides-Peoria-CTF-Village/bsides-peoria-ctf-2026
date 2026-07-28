This challenge was honestly something I wanted to do for a while now, make a challenge in which the solution feels unintended. The solution is pretty simple honestly, find a challenge that lets you upload files that return the proper filetype, upload JS to it, and use that challenge to bypass the CSP.

The other challenge is a file upload vulnerability (not out yet), and you upload you xss payload there to exfil. The next step is the connect src, but you can use the same file upload challenge to post data to it and create a file that you can view.

Believe it or not, I got parts of this idea from Okta's CSP. You can exfil data to Mixpanel, which is allowed in their own CSP.