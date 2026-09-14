type token = { text : string; line : int; column : int }
type expr =
  | Number of int32 | Variable of string | Negate of expr
  | Binary of string * expr * expr | Let of string * expr * expr
  | If of expr * expr * expr | Call of string * expr list
type func = { name : string; params : string list; body : expr }
type program = { functions : func list; expression : expr }
exception Error of string * string * int * int

let quote text =
  let out = Buffer.create 32 in
  Buffer.add_char out '"';
  String.iter (function
    | '"' -> Buffer.add_string out "\\\""
    | '\\' -> Buffer.add_string out "\\\\"
    | '\n' -> Buffer.add_string out "\\n"
    | '\r' -> Buffer.add_string out "\\r"
    | '\t' -> Buffer.add_string out "\\t"
    | c when Char.code c < 32 -> Buffer.add_string out (Printf.sprintf "\\u%04x" (Char.code c))
    | c -> Buffer.add_char out c) text;
  Buffer.add_char out '"'; Buffer.contents out
let obj fields = "{" ^ String.concat "," (List.map (fun (k,v) -> quote k ^ ":" ^ v) fields) ^ "}"
let arr items = "[" ^ String.concat "," items ^ "]"
let digit c = c >= '0' && c <= '9'
let letter c = (c >= 'a' && c <= 'z') || (c >= 'A' && c <= 'Z') || c = '_'

let lex source =
  let n = String.length source in
  let rec scan i line column acc =
    if i = n then List.rev ({text="<eof>";line;column}::acc)
    else match source.[i] with
    | ' ' | '\t' | '\r' -> scan (i+1) line (column+1) acc
    | '\n' -> scan (i+1) (line+1) 1 acc
    | '#' -> let j = ref i in while !j < n && source.[!j] <> '\n' do incr j done; scan !j line (column + !j-i) acc
    | c ->
      let j = ref (i+1) in
      if digit c then (while !j<n && digit source.[!j] do incr j done)
      else if letter c then (while !j<n && (letter source.[!j] || digit source.[!j]) do incr j done)
      else if List.mem c ['=';'!';'<';'>'] && !j<n && source.[!j]='=' then incr j
      else if not (List.mem c ['+';'-';'*';'/';'%';'(';')';',';';';'=';'<';'>']) then
        raise (Error ("lex", "Unexpected character " ^ String.make 1 c, line, column));
      let text = String.sub source i (!j-i) in
      scan !j line (column + !j-i) ({text;line;column}::acc)
  in Array.of_list (scan 0 1 1 [])

let parse tokens =
  let position = ref 0 in
  let peek () = tokens.(!position).text in
  let fail message = let t=tokens.(!position) in raise(Error("parse",message,t.line,t.column)) in
  let take () = let t=peek() in if t<>"<eof>" then incr position; t in
  let expect value = if peek()<>value then fail ("Expected " ^ value ^ ", found " ^ peek()) else ignore(take()) in
  let identifier () =
    let name=peek() in
    if name="" || not(letter name.[0]) || List.mem name ["fn";"let";"in";"if";"then";"else"] then fail "Expected an identifier";
    ignore(take()); name
  in
  let rec expression () =
    match peek() with
    | "let" -> ignore(take()); let name=identifier() in expect "="; let value=expression() in expect "in"; Let(name,value,expression())
    | "if" -> ignore(take()); let condition=expression() in expect "then"; let yes=expression() in expect "else"; If(condition,yes,expression())
    | _ -> comparison ()
  and comparison () = chain sum ["==";"!=";"<";">";"<=";">="]
  and sum () = chain product ["+";"-"]
  and product () = chain unary ["*";"/";"%"]
  and chain next operators =
    let left=next() in
    let rec rest left = if List.mem (peek()) operators then (let op=take() in let right=next() in rest(Binary(op,left,right))) else left in
    rest left
  and unary () =
    if peek()="-" then (ignore(take()); if peek()="2147483648" then (ignore(take());Number Int32.min_int) else Negate(unary()))
    else atom ()
  and atom () =
    let text=peek() in
    if text="(" then (ignore(take());let value=expression() in expect ")";value)
    else if text<>"" && digit text.[0] then (
      let number = try Int32.of_string text with Failure _ -> fail "Integer literal is outside signed 32-bit range" in
      ignore(take()); Number number)
    else if text<>"" && letter text.[0] then (
      let name=identifier() in
      if peek()<>"(" then Variable name else (
        ignore(take());
        let rec args acc = let value=expression() in if peek()="," then (ignore(take());args(value::acc)) else List.rev(value::acc) in
        let values=if peek()=")" then [] else args [] in expect ")";Call(name,values)))
    else fail ("Expected an expression, found " ^ text)
  in
  let rec functions acc =
    if peek()<>"fn" then List.rev acc else (
      ignore(take());let name=identifier() in expect "(";
      let rec params acc = let name=identifier() in if peek()="," then (ignore(take());params(name::acc)) else List.rev(name::acc) in
      let args=if peek()=")" then [] else params [] in
      expect ")";expect "=";let body=expression() in expect ";";
      functions({name;params=args;body}::acc))
  in
  let functions=functions [] in let expression=expression() in expect "<eof>"; {functions;expression}

let check program =
  let error message = raise(Error("semantic",message,0,0)) in
  let signatures=Hashtbl.create 16 in
  List.iter (fun f ->
    if Hashtbl.mem signatures f.name then error("Duplicate function " ^ f.name);
    if List.length f.params>4 then error "Functions accept at most four parameters";
    if List.length (List.sort_uniq String.compare f.params) <> List.length f.params then error("Duplicate parameter in " ^ f.name);
    Hashtbl.add signatures f.name (List.length f.params)) program.functions;
  let rec walk depth env = function
    | _ when depth>100 -> error "Expression nesting exceeds 100 levels"
    | Number _ -> ()
    | Variable name -> if not(List.mem name env) then error("Undefined variable " ^ name)
    | Negate x -> walk (depth+1) env x
    | Binary(_,a,b) -> walk (depth+1) env a;walk (depth+1) env b
    | Let(name,value,body) -> walk (depth+1) env value;walk (depth+1) (name::env) body
    | If(c,a,b) -> List.iter (walk (depth+1) env) [c;a;b]
    | Call(name,args) ->
      if not(Hashtbl.mem signatures name) then error("Undefined function " ^ name);
      if Hashtbl.find signatures name <> List.length args then error("Wrong argument count for " ^ name);
      List.iter (walk (depth+1) env) args
  in
  List.iter (fun f -> walk 0 f.params f.body) program.functions;
  walk 0 [] program.expression

let rec expr_json = function
  | Number n -> obj ["kind",quote "number";"value",Int32.to_string n]
  | Variable n -> obj ["kind",quote "variable";"name",quote n]
  | Negate x -> obj ["kind",quote "negate";"value",expr_json x]
  | Binary(op,a,b) -> obj ["kind",quote "binary";"operator",quote op;"left",expr_json a;"right",expr_json b]
  | Let(n,a,b) -> obj ["kind",quote "let";"name",quote n;"value",expr_json a;"body",expr_json b]
  | If(c,a,b) -> obj ["kind",quote "if";"condition",expr_json c;"then",expr_json a;"else",expr_json b]
  | Call(n,args) -> obj ["kind",quote "call";"name",quote n;"arguments",arr(List.map expr_json args)]
let program_json program = obj ["functions",arr(List.map (fun f -> obj ["name",quote f.name;"params",arr(List.map quote f.params);"body",expr_json f.body]) program.functions);"expression",expr_json program.expression]
