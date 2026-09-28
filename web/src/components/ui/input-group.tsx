import { cn } from "cn"

function InputGroup({ className, ...props }: React.ComponentProps<"div">) {
  return (
    <div
      data-slot="input-group"
      className={cn(
        "flex h-8 w-full min-w-0 items-stretch rounded-lg border border-input bg-transparent transition-colors outline-none has-data-[slot=input-group-control]:focus-within:border-ring has-data-[slot=input-group-control]:focus-within:ring-3 has-data-[slot=input-group-control]:focus-within:ring-ring/50 has-aria-invalid:border-destructive has-aria-invalid:ring-3 has-aria-invalid:ring-destructive/20 disabled:pointer-events-none disabled:opacity-50 md:text-sm dark:bg-input/30",
        className
      )}
      {...props}
    />
  )
}

function InputGroupAddon({
  className,
  align = "inline-start",
  ...props
}: React.ComponentProps<"div"> & {
  align?: "inline-start" | "inline-end" | "block-start" | "block-end"
}) {
  return (
    <div
      data-slot="input-group-addon"
      data-align={align}
      className={cn(
        "flex items-center gap-1.5 text-muted-foreground select-none",
        "data-[align=inline-start]:pl-2.5 data-[align=inline-end]:pr-2.5",
        "data-[align=block-start]:px-2.5 data-[align=block-start]:pt-1.5",
        "data-[align=block-end]:px-2.5 data-[align=block-end]:pb-1.5",
        "[&_svg:not([class*='size-'])]:size-3.5 [&_svg]:shrink-0",
        className
      )}
      {...props}
    />
  )
}

function InputGroupButton({
  className,
  size = "xs",
  variant = "ghost",
  ...props
}: React.ComponentProps<"button"> & {
  size?: "xs" | "icon-xs" | "sm" | "icon-sm"
  variant?: "default" | "destructive" | "outline" | "secondary" | "ghost" | "link"
}) {
  return (
    <button
      data-slot="input-group-button"
      data-size={size}
      data-variant={variant}
      className={cn(
        "inline-flex shrink-0 cursor-pointer items-center justify-center gap-1 rounded-md text-xs font-medium whitespace-nowrap transition-colors outline-none select-none focus-visible:ring-3 focus-visible:ring-ring/50 disabled:pointer-events-none disabled:opacity-50",
        "data-[variant=ghost]:hover:bg-muted data-[variant=ghost]:hover:text-foreground",
        "data-[variant=outline]:border data-[variant=outline]:border-border data-[variant=outline]:bg-background data-[variant=outline]:hover:bg-muted",
        "data-[variant=default]:bg-primary data-[variant=default]:text-primary-foreground data-[variant=default]:hover:bg-primary/80",
        "data-[size=xs]:h-6 data-[size=xs]:px-2 data-[size=xs]:text-xs",
        "data-[size=sm]:h-7 data-[size=sm]:px-2.5",
        "data-[size=icon-xs]:size-6 data-[size=icon-sm]:size-7",
        "[&_svg:not([class*='size-'])]:size-3.5 [&_svg]:shrink-0",
        className
      )}
      {...props}
    />
  )
}

function InputGroupInput({ className, ...props }: React.ComponentProps<"input">) {
  return (
    <input
      data-slot="input-group-control"
      className={cn(
        "min-w-0 flex-1 bg-transparent px-2 py-1 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed",
        className
      )}
      {...props}
    />
  )
}

function InputGroupText({ className, ...props }: React.ComponentProps<"span">) {
  return (
    <span
      data-slot="input-group-text"
      className={cn("text-xs whitespace-nowrap text-muted-foreground", className)}
      {...props}
    />
  )
}

export { InputGroup, InputGroupAddon, InputGroupButton, InputGroupInput, InputGroupText }
