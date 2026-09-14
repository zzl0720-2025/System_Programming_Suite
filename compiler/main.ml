open Syntax

let () =
  try
    let source=Buffer.create 256 in
    (try while true do Buffer.add_string source (input_line stdin);Buffer.add_char source '\n' done with End_of_file -> ());
    let tokens=lex(Buffer.contents source) in
    if Array.length tokens>2048 then raise(Error("parse","Program exceeds 2048 tokens",0,0));
    let program=parse tokens in check program;
    let reference=Eval.evaluate program in
    let assembly=Codegen.generate program in
    let token_json=Array.to_list tokens |> List.filter(fun t->t.text<>"<eof>") |> List.map(fun t->obj["text",quote t.text;"line",string_of_int t.line;"column",string_of_int t.column]) in
    print_endline(obj["tokens",arr token_json;"ast",program_json program;"reference_result",Int32.to_string reference;"assembly",quote assembly])
  with
  | Error(stage,message,line,column) ->
    print_endline(obj["error",obj["stage",quote stage;"message",quote message;"line",string_of_int line;"column",string_of_int column]]);exit 2
  | Stack_overflow -> print_endline(obj["error",obj["stage",quote "parse";"message",quote "Program nesting is too deep"]]);exit 2
