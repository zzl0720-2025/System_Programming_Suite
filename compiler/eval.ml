open Syntax

let evaluate program =
  let fuel=ref 50000 in
  let truth value = if value then 1l else 0l in
  let rec run depth env expression =
    decr fuel;
    if !fuel<0 || depth>256 then raise(Error("reference","Evaluation limit reached",0,0));
    let sub=run (depth+1) env in
    match expression with
    | Number n -> n
    | Variable name -> List.assoc name env
    | Negate x -> Int32.neg(sub x)
    | Let(name,value,body) -> let value=sub value in run (depth+1) ((name,value)::env) body
    | If(c,a,b) -> if sub c <> 0l then sub a else sub b
    | Call(name,args) ->
      let f=List.find (fun f->f.name=name) program.functions in
      let values=List.map sub args in run (depth+1) (List.combine f.params values) f.body
    | Binary(op,a,b) ->
      let a=sub a in let b=sub b in
      match op with
      | "+" -> Int32.add a b | "-" -> Int32.sub a b | "*" -> Int32.mul a b
      | "/" -> if b=0l then -1l else if a=Int32.min_int && b = -1l then a else Int32.div a b
      | "%" -> if b=0l then a else if a=Int32.min_int && b = -1l then 0l else Int32.rem a b
      | "==" -> truth(a=b) | "!=" -> truth(a<>b) | "<" -> truth(a<b) | ">" -> truth(a>b)
      | "<=" -> truth(a<=b) | ">=" -> truth(a>=b) | _ -> assert false
  in run 0 [] program.expression
