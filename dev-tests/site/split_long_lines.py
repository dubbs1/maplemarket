import sys
s=open(sys.argv[1]).read(); LIMIT=int(sys.argv[2]) if len(sys.argv)>2 else 140
out=[]; st=[]; brace=[]; i=0; n=len(s); col=0; indent=0; prev=''   # prev = last significant code char
def emit(t):
    global col, indent
    for ch in t:
        out.append(ch)
        if ch=='\n': col=0
        else: col+=1
def line_indent():
    j=len(out)-1; k=0
    while j>=0 and out[j]!='\n': j-=1
    j+=1
    while j<len(out) and out[j]==' ': k+=1; j+=1
    return k
while i<n:
    c=s[i]; top=st[-1] if st else None
    if top in ("'",'"','T'):
        if c=='\\': emit(s[i:i+2]); i+=2; continue
        if (top=='T' and c=='`') or (top!='T' and c==top):
            st.pop(); emit(c); i+=1; prev=c; continue
        if top=='T' and c=='$' and s[i+1]=='{': st.append('E'); brace.append(0); emit('${'); i+=2; prev='{'; continue
        emit(c); i+=1
        # cut after a tag end when this physical line is long, and the rest of this line is long too
        if (c=='>' and col>LIMIT) or (c==' ' and col>LIMIT+40) and s[i] not in '`\'"\n':
            rest=s.find('\n',i); rest=(n if rest<0 else rest)-i
            if rest>20:
                q='`' if top=='T' else top
                j=len(out)-1
                while j>=0 and out[j]!='\n': j-=1
                cont=''.join(out[max(0,j-2):j]).endswith(' +')
                emit(q+' +\n'+' '*(line_indent()+(0 if cont else 2))+q)
        continue
    # code
    if c in "'\"": st.append(c); emit(c); i+=1; continue
    if c=='`': st.append('T'); emit(c); i+=1; continue
    if c=='/' and s[i+1]=='/': j=s.find('\n',i); emit(s[i:j]); i=j; continue
    if c=='/' and s[i+1]=='*': j=s.find('*/',i)+2; emit(s[i:j]); i=j; continue
    if c=='/' and (prev=='' or prev in '(,=:[!&|?{};+-*%<>~^' or s[max(0,i-7):i].rstrip().endswith('return')):
        j=i+1; cls=False
        while True:
            d=s[j]
            if d=='\\': j+=2; continue
            if d=='[': cls=True
            elif d==']': cls=False
            elif d=='/' and not cls: break
            j+=1
        j+=1
        while j<n and s[j].isalpha(): j+=1
        emit(s[i:j]); i=j; prev='/'; continue
    if top=='E':
        if c=='{': brace[-1]+=1
        elif c=='}':
            if brace[-1]==0: st.pop(); brace.pop(); emit(c); i+=1; prev='}'; continue
            brace[-1]-=1
    emit(c); i+=1
    if not c.isspace(): prev=c
assert not st, st
print(''.join(out),end='')
